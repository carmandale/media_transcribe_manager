/**
 * API endpoint for generating and serving video thumbnails
 */

import { NextRequest, NextResponse } from 'next/server';
import { promises as fs } from 'fs';
import path from 'path';
import { 
  generateInterviewThumbnail, 
  thumbnailExists, 
  getThumbnailPath,
  needsRegeneration 
} from '@/lib/thumbnail-generator';
import { 
  detectMediaType, 
  getAbsoluteMediaPath, 
  mediaFileExists 
} from '@/lib/media-utils';

interface ThumbnailParams {
  id: string;
}

/**
 * GET /api/thumbnails/[id]
 * Generate or serve a thumbnail for an interview
 */
export async function GET(
  request: NextRequest,
  { params }: { params: Promise<ThumbnailParams> }
) {
  try {
    const { id } = await params;
    
    if (!id) {
      return NextResponse.json(
        { error: 'Interview ID is required' },
        { status: 400 }
      );
    }

    // Get query parameters
    const searchParams = request.nextUrl.searchParams;
    const force = searchParams.get('force') === 'true';
    const width = searchParams.get('width') ? parseInt(searchParams.get('width')!) : undefined;
    const height = searchParams.get('height') ? parseInt(searchParams.get('height')!) : undefined;
    const quality = searchParams.get('quality') ? parseInt(searchParams.get('quality')!) : undefined;

    // Load interview manifest to get video path
    const manifestPath = path.join(process.cwd(), 'public', 'manifest.json');
    
    let interviews;
    try {
      const manifestContent = await fs.readFile(manifestPath, 'utf-8');
      interviews = JSON.parse(manifestContent);
    } catch (error) {
      console.error('Error loading interviews manifest:', error);
      return NextResponse.json(
        { 
          error: 'Could not load interviews data',
          details: error instanceof Error ? error.message : 'Unknown error',
          manifestPath: manifestPath
        },
        { status: 500 }
      );
    }

    // Find the interview
    const interview = interviews.find((i: any) => i.id === id);
    if (!interview) {
      return NextResponse.json(
        { error: 'Interview not found' },
        { status: 404 }
      );
    }

    const videoPath = interview.assets?.video;
    if (!videoPath) {
      return NextResponse.json(
        { error: 'No video file associated with this interview' },
        { status: 404 }
      );
    }

    // Check if video file exists
    if (!(await mediaFileExists(videoPath))) {
      return NextResponse.json(
        { error: 'Video file not found' },
        { status: 404 }
      );
    }

    // Detect media type
    const absoluteVideoPath = getAbsoluteMediaPath(videoPath);
    const mediaType = await detectMediaType(absoluteVideoPath);
    
    if (mediaType === 'audio') {
      return NextResponse.json(
        { 
          error: 'Cannot generate thumbnail for audio-only content',
          mediaType: 'audio'
        },
        { status: 400 }
      );
    }

    if (mediaType === 'unknown') {
      return NextResponse.json(
        { error: 'Unknown media type' },
        { status: 400 }
      );
    }

    // Check if thumbnail exists and if regeneration is needed
    const thumbnailPath = getThumbnailPath(id);
    const exists = await thumbnailExists(id);
    const needsRegen = exists ? await needsRegeneration(id, videoPath) : true;

    if (exists && !needsRegen && !force) {
      // Return existing thumbnail info
      return NextResponse.json({
        success: true,
        thumbnailPath,
        cached: true,
        mediaType: 'video'
      });
    }

    // Generate thumbnail
    const result = await generateInterviewThumbnail(id, videoPath, {
      width,
      height,
      quality,
      force: force || needsRegen
    });

    if (!result.success) {
      console.error('Thumbnail generation failed:', result.error);
      return NextResponse.json(
        { 
          error: result.error || 'Failed to generate thumbnail',
          mediaType: 'video'
        },
        { status: 500 }
      );
    }

    return NextResponse.json({
      success: true,
      thumbnailPath: result.thumbnailPath,
      cached: result.cached || false,
      mediaType: 'video'
    });

  } catch (error) {
    console.error('Error in thumbnail API:', error);
    return NextResponse.json(
      { error: 'Internal server error' },
      { status: 500 }
    );
  }
}

/**
 * DELETE /api/thumbnails/[id]
 * Delete a thumbnail for an interview
 */
export async function DELETE(
  request: NextRequest,
  { params }: { params: ThumbnailParams }
) {
  try {
    const { id } = params;
    
    if (!id) {
      return NextResponse.json(
        { error: 'Interview ID is required' },
        { status: 400 }
      );
    }

    const exists = await thumbnailExists(id);
    if (!exists) {
      return NextResponse.json(
        { error: 'Thumbnail not found' },
        { status: 404 }
      );
    }

    // Delete thumbnail file
    const thumbnailPath = getAbsoluteMediaPath(getThumbnailPath(id));
    await fs.unlink(thumbnailPath);

    return NextResponse.json({
      success: true,
      message: 'Thumbnail deleted successfully'
    });

  } catch (error) {
    console.error('Error deleting thumbnail:', error);
    return NextResponse.json(
      { error: 'Failed to delete thumbnail' },
      { status: 500 }
    );
  }
}
