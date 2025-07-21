/**
 * Media utilities for file type detection and media processing
 */

import { promises as fs } from 'fs';
import { exec } from 'child_process';
import { promisify } from 'util';
import path from 'path';

const execAsync = promisify(exec);

export interface MediaInfo {
  hasVideo: boolean;
  hasAudio: boolean;
  duration: number;
  format: string;
  videoCodec?: string;
  audioCodec?: string;
  width?: number;
  height?: number;
}

/**
 * Common video file extensions
 */
const VIDEO_EXTENSIONS = [
  '.mp4', '.avi', '.mov', '.mkv', '.wmv', '.flv', '.webm', '.m4v', '.3gp', '.ogv'
];

/**
 * Common audio file extensions
 */
const AUDIO_EXTENSIONS = [
  '.mp3', '.wav', '.flac', '.aac', '.ogg', '.wma', '.m4a', '.opus'
];

/**
 * Check if a file path appears to be a video file based on extension
 */
export function isVideoFileByExtension(filePath: string): boolean {
  const ext = path.extname(filePath).toLowerCase();
  return VIDEO_EXTENSIONS.includes(ext);
}

/**
 * Check if a file path appears to be an audio file based on extension
 */
export function isAudioFileByExtension(filePath: string): boolean {
  const ext = path.extname(filePath).toLowerCase();
  return AUDIO_EXTENSIONS.includes(ext);
}

/**
 * Check if FFmpeg is available on the system
 */
export async function isFFmpegAvailable(): Promise<boolean> {
  try {
    await execAsync('ffmpeg -version');
    return true;
  } catch (error) {
    console.warn('FFmpeg not available:', error);
    return false;
  }
}

/**
 * Get detailed media information using FFprobe
 */
export async function getMediaInfo(filePath: string): Promise<MediaInfo | null> {
  try {
    // Check if file exists
    await fs.access(filePath);
    
    // Use FFprobe to get media information
    const command = `ffprobe -v quiet -print_format json -show_format -show_streams "${filePath}"`;
    const { stdout } = await execAsync(command);
    const data = JSON.parse(stdout);
    
    const videoStream = data.streams?.find((stream: any) => stream.codec_type === 'video');
    const audioStream = data.streams?.find((stream: any) => stream.codec_type === 'audio');
    
    return {
      hasVideo: !!videoStream,
      hasAudio: !!audioStream,
      duration: parseFloat(data.format?.duration || '0'),
      format: data.format?.format_name || 'unknown',
      videoCodec: videoStream?.codec_name,
      audioCodec: audioStream?.codec_name,
      width: videoStream?.width,
      height: videoStream?.height,
    };
  } catch (error) {
    console.error('Error getting media info:', error);
    return null;
  }
}

/**
 * Determine if a media file is video or audio-only
 * Falls back to extension-based detection if FFprobe fails
 */
export async function detectMediaType(filePath: string): Promise<'video' | 'audio' | 'unknown'> {
  // First try to get detailed media info
  const mediaInfo = await getMediaInfo(filePath);
  
  if (mediaInfo) {
    if (mediaInfo.hasVideo) {
      return 'video';
    } else if (mediaInfo.hasAudio) {
      return 'audio';
    }
  }
  
  // Fallback to extension-based detection
  if (isVideoFileByExtension(filePath)) {
    return 'video';
  } else if (isAudioFileByExtension(filePath)) {
    return 'audio';
  }
  
  return 'unknown';
}

/**
 * Get the absolute file path for a media file given its relative path
 */
export function getAbsoluteMediaPath(relativePath: string): string {
  // Remove leading slash if present
  const cleanPath = relativePath.startsWith('/') ? relativePath.slice(1) : relativePath;
  
  // Construct absolute path to the public directory
  return path.join(process.cwd(), 'public', cleanPath);
}

/**
 * Check if a media file exists
 */
export async function mediaFileExists(relativePath: string): Promise<boolean> {
  try {
    const absolutePath = getAbsoluteMediaPath(relativePath);
    await fs.access(absolutePath);
    return true;
  } catch {
    return false;
  }
}

/**
 * Get the duration of a media file in seconds
 */
export async function getMediaDuration(filePath: string): Promise<number> {
  const mediaInfo = await getMediaInfo(filePath);
  return mediaInfo?.duration || 0;
}

