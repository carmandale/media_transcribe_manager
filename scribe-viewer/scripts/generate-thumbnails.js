#!/usr/bin/env node

const fs = require('fs').promises;
const path = require('path');
const { exec } = require('child_process');
const { promisify } = require('util');

const execAsync = promisify(exec);

// Configuration
const THUMBNAIL_WIDTH = 320;
const THUMBNAIL_HEIGHT = 240; // 4:3 aspect ratio
const THUMBNAIL_TIME = '00:00:30'; // 30 seconds into video for better frame
const MANIFEST_PATH = path.join(__dirname, '../public/manifest.json');
const THUMBNAILS_DIR = path.join(__dirname, '../public/thumbnails');
const PUBLIC_DIR = path.join(__dirname, '../public');

// Ensure thumbnails directory exists
async function ensureDirectory(dir) {
  try {
    await fs.mkdir(dir, { recursive: true });
  } catch (error) {
    console.error(`Error creating directory ${dir}:`, error);
  }
}

// Generate a single thumbnail
async function generateThumbnail(interview) {
  const { id, assets } = interview;
  const videoPath = assets?.video;
  
  if (!videoPath) {
    console.log(`⚠️  No video for interview ${id}`);
    return false;
  }

  // Skip audio files
  if (videoPath.toLowerCase().match(/\.(mp3|wav|m4a|aac|ogg|flac)$/)) {
    console.log(`🎵 Skipping audio file for ${id}: ${path.basename(videoPath)}`);
    return 'audio';
  }

  // Construct absolute path
  const absoluteVideoPath = path.join(PUBLIC_DIR, videoPath);
  const thumbnailPath = path.join(THUMBNAILS_DIR, `${id}.jpg`);

  // Check if thumbnail already exists
  try {
    await fs.access(thumbnailPath);
    console.log(`✓ Thumbnail exists for ${id}`);
    return true;
  } catch {
    // Thumbnail doesn't exist, generate it
  }

  // Check if video file exists
  try {
    await fs.access(absoluteVideoPath);
  } catch {
    console.log(`❌ Video file not found for ${id}: ${videoPath}`);
    return false;
  }

  // Generate thumbnail using ffmpeg with smart frame selection
  // Use scale2ref to maintain aspect ratio and pad to 4:3
  const ffmpegCommand = `ffmpeg -i "${absoluteVideoPath}" -ss ${THUMBNAIL_TIME} -vframes 1 -vf "scale=${THUMBNAIL_WIDTH}:${THUMBNAIL_HEIGHT}:force_original_aspect_ratio=decrease,pad=${THUMBNAIL_WIDTH}:${THUMBNAIL_HEIGHT}:(ow-iw)/2:(oh-ih)/2:black" -q:v 2 "${thumbnailPath}" -y`;
  
  try {
    console.log(`⏳ Generating thumbnail for ${id}...`);
    await execAsync(ffmpegCommand);
    console.log(`✅ Generated thumbnail for ${id}`);
    return true;
  } catch (error) {
    // Try multiple fallback times for short videos or black frames
    const fallbackTimes = ['00:00:15', '00:00:05', '00:00:02'];
    
    for (const time of fallbackTimes) {
      try {
        const fallbackCommand = ffmpegCommand.replace(`-ss ${THUMBNAIL_TIME}`, `-ss ${time}`);
        await execAsync(fallbackCommand);
        console.log(`✅ Generated thumbnail for ${id} (using ${time} mark)`);
        return true;
      } catch (fallbackError) {
        // Continue to next fallback time
      }
    }
    
    console.error(`❌ Failed to generate thumbnail for ${id}:`, error.message);
    return false;
  }
}

// Main function
async function main() {
  console.log('🎬 Starting thumbnail generation...\n');

  // Ensure thumbnails directory exists
  await ensureDirectory(THUMBNAILS_DIR);

  // Load manifest
  let manifest;
  try {
    const manifestContent = await fs.readFile(MANIFEST_PATH, 'utf-8');
    manifest = JSON.parse(manifestContent);
  } catch (error) {
    console.error('❌ Error loading manifest:', error);
    process.exit(1);
  }

  console.log(`📋 Found ${manifest.length} interviews in manifest\n`);

  // Process each interview
  let successCount = 0;
  let audioCount = 0;
  let errorCount = 0;

  for (const interview of manifest) {
    const result = await generateThumbnail(interview);
    if (result === true) {
      successCount++;
    } else if (result === 'audio') {
      audioCount++;
    } else if (result === false) {
      errorCount++;
    }
  }

  // Summary
  console.log('\n📊 Summary:');
  console.log(`✅ Video thumbnails generated: ${successCount}`);
  console.log(`🎵 Audio files skipped: ${audioCount}`);
  console.log(`❌ Errors: ${errorCount}`);
  console.log(`📁 Total interviews: ${manifest.length}`);
  console.log('\n✨ Thumbnail generation complete!');
}

// Run the script
main().catch(console.error);