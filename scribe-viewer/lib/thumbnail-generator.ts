/**
 * Video thumbnail generation utility using FFmpeg
 */

import { promises as fs } from 'fs';
import { exec } from 'child_process';
import { promisify } from 'util';
import path from 'path';
import { getMediaInfo, getAbsoluteMediaPath, isFFmpegAvailable } from './media-utils';

const execAsync = promisify(exec);

export interface ThumbnailOptions {
  /** Width of the thumbnail (height will be calculated to maintain aspect ratio) */
  width?: number;
  /** Height of the thumbnail (width will be calculated to maintain aspect ratio) */
  height?: number;
  /** Quality of the JPEG thumbnail (1-31, lower is better quality) */
  quality?: number;
  /** Timestamp to extract thumbnail from (in seconds). If not provided, uses middle of video */
  timestamp?: number;
  /** Force regeneration even if thumbnail already exists */
  force?: boolean;
}

export interface ThumbnailResult {
  success: boolean;
  thumbnailPath?: string;
  error?: string;
  cached?: boolean;
}

const DEFAULT_OPTIONS: Required<Omit<ThumbnailOptions, 'timestamp' | 'force'>> = {
  width: 320,
  height: 180,
  quality: 2, // High quality
};

/**
 * Generate a thumbnail for a video file
 */
export async function generateThumbnail(
  videoPath: string,
  outputPath: string,
  options: ThumbnailOptions = {}
): Promise<ThumbnailResult> {
  try {
    // Check if FFmpeg is available
    if (!(await isFFmpegAvailable())) {
      return {
        success: false,
        error: 'FFmpeg is not available on this system'
      };
    }

    // Merge options with defaults
    const opts = { ...DEFAULT_OPTIONS, ...options };

    // Check if thumbnail already exists and force is not set
    if (!opts.force) {
      try {
        await fs.access(outputPath);
        return {
          success: true,
          thumbnailPath: outputPath,
          cached: true
        };
      } catch {
        // File doesn't exist, continue with generation
      }
    }

    // Get video information
    const mediaInfo = await getMediaInfo(videoPath);
    if (!mediaInfo) {
      return {
        success: false,
        error: 'Could not get media information'
      };
    }

    if (!mediaInfo.hasVideo) {
      return {
        success: false,
        error: 'File does not contain video streams'
      };
    }

    // Calculate timestamp (middle of video if not provided)
    const timestamp = opts.timestamp ?? (mediaInfo.duration / 2);

    // Ensure output directory exists
    const outputDir = path.dirname(outputPath);
    await fs.mkdir(outputDir, { recursive: true });

    // Build FFmpeg command
    const command = [
      'ffmpeg',
      '-y', // Overwrite output file
      `-ss ${timestamp}`, // Seek to timestamp
      `-i "${videoPath}"`, // Input file
      '-vframes 1', // Extract only one frame
      `-vf scale=${opts.width}:${opts.height}:force_original_aspect_ratio=decrease,pad=${opts.width}:${opts.height}:(ow-iw)/2:(oh-ih)/2:black`, // Scale and pad to exact dimensions
      `-q:v ${opts.quality}`, // Set JPEG quality
      `"${outputPath}"` // Output file
    ].join(' ');

    // Execute FFmpeg command
    await execAsync(command);

    // Verify the thumbnail was created
    try {
      await fs.access(outputPath);
      return {
        success: true,
        thumbnailPath: outputPath
      };
    } catch {
      return {
        success: false,
        error: 'Thumbnail file was not created'
      };
    }

  } catch (error) {
    console.error('Error generating thumbnail:', error);
    return {
      success: false,
      error: error instanceof Error ? error.message : 'Unknown error occurred'
    };
  }
}

/**
 * Generate thumbnail for an interview video
 */
export async function generateInterviewThumbnail(
  interviewId: string,
  videoRelativePath: string,
  options: ThumbnailOptions = {}
): Promise<ThumbnailResult> {
  try {
    // Get absolute paths
    const videoAbsolutePath = getAbsoluteMediaPath(videoRelativePath);
    const thumbnailRelativePath = `/media/${interviewId}/thumbnail.jpg`;
    const thumbnailAbsolutePath = getAbsoluteMediaPath(thumbnailRelativePath);

    // Generate thumbnail
    const result = await generateThumbnail(videoAbsolutePath, thumbnailAbsolutePath, options);

    // Update result with relative path for web serving
    if (result.success && result.thumbnailPath) {
      result.thumbnailPath = thumbnailRelativePath;
    }

    return result;
  } catch (error) {
    console.error('Error generating interview thumbnail:', error);
    return {
      success: false,
      error: error instanceof Error ? error.message : 'Unknown error occurred'
    };
  }
}

/**
 * Check if a thumbnail exists for an interview
 */
export async function thumbnailExists(interviewId: string): Promise<boolean> {
  try {
    const thumbnailPath = getAbsoluteMediaPath(`/media/${interviewId}/thumbnail.jpg`);
    await fs.access(thumbnailPath);
    return true;
  } catch {
    return false;
  }
}

/**
 * Get the thumbnail path for an interview (relative path for web serving)
 */
export function getThumbnailPath(interviewId: string): string {
  return `/media/${interviewId}/thumbnail.jpg`;
}

/**
 * Delete a thumbnail file
 */
export async function deleteThumbnail(interviewId: string): Promise<boolean> {
  try {
    const thumbnailPath = getAbsoluteMediaPath(`/media/${interviewId}/thumbnail.jpg`);
    await fs.unlink(thumbnailPath);
    return true;
  } catch (error) {
    console.error('Error deleting thumbnail:', error);
    return false;
  }
}

/**
 * Get thumbnail modification time for cache validation
 */
export async function getThumbnailModTime(interviewId: string): Promise<Date | null> {
  try {
    const thumbnailPath = getAbsoluteMediaPath(`/media/${interviewId}/thumbnail.jpg`);
    const stats = await fs.stat(thumbnailPath);
    return stats.mtime;
  } catch {
    return null;
  }
}

/**
 * Check if thumbnail needs regeneration based on source video modification time
 */
export async function needsRegeneration(
  interviewId: string,
  videoRelativePath: string
): Promise<boolean> {
  try {
    const thumbnailModTime = await getThumbnailModTime(interviewId);
    if (!thumbnailModTime) {
      return true; // Thumbnail doesn't exist
    }

    const videoPath = getAbsoluteMediaPath(videoRelativePath);
    const videoStats = await fs.stat(videoPath);
    
    // Regenerate if video is newer than thumbnail
    return videoStats.mtime > thumbnailModTime;
  } catch {
    return true; // Error accessing files, assume regeneration needed
  }
}

