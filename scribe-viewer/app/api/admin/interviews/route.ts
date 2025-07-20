/**
 * Admin API routes for interview metadata management
 * Provides CRUD operations for interview data with proper validation
 */

import { NextRequest, NextResponse } from 'next/server';
import { readFile, writeFile } from 'fs/promises';
import { join } from 'path';
import { Interview } from '@/lib/types';
import { withAdminAuth, getAuthenticatedUser } from '@/lib/auth';

const MANIFEST_PATH = join(process.cwd(), 'public', 'manifest.json');
const MANIFEST_MIN_PATH = join(process.cwd(), 'public', 'manifest.min.json');

// Helper function to load manifest
async function loadManifest(): Promise<Interview[]> {
  try {
    const fileContents = await readFile(MANIFEST_PATH, 'utf8');
    return JSON.parse(fileContents);
  } catch (error) {
    console.error('Failed to load manifest:', error);
    return [];
  }
}

// Helper function to save manifest
async function saveManifest(interviews: Interview[]): Promise<void> {
  try {
    // Save full manifest
    const jsonContent = JSON.stringify(interviews, null, 2);
    await writeFile(MANIFEST_PATH, jsonContent, 'utf8');
    
    // Save minified manifest for gallery (only id and metadata)
    const minifiedInterviews = interviews.map(interview => ({
      id: interview.id,
      metadata: interview.metadata
    }));
    const minJsonContent = JSON.stringify(minifiedInterviews, null, 2);
    await writeFile(MANIFEST_MIN_PATH, minJsonContent, 'utf8');
  } catch (error) {
    console.error('Failed to save manifest:', error);
    throw new Error('Failed to save manifest');
  }
}

// Helper function to validate interview data
function validateInterviewData(data: Partial<Interview>): string[] {
  const errors: string[] = [];
  
  if (data.metadata) {
    if (!data.metadata.interviewee || data.metadata.interviewee.trim().length === 0) {
      errors.push('Interviewee name is required');
    }
    
    if (!data.metadata.summary || data.metadata.summary.trim().length === 0) {
      errors.push('Summary is required');
    }
    
    if (data.metadata.date && !isValidDate(data.metadata.date)) {
      errors.push('Invalid date format (expected YYYY-MM-DD)');
    }
  }
  
  return errors;
}

// Helper function to validate date format
function isValidDate(dateString: string): boolean {
  const regex = /^\d{4}-\d{2}-\d{2}$/;
  if (!regex.test(dateString)) return false;
  
  const date = new Date(dateString);
  return date instanceof Date && !isNaN(date.getTime());
}

// GET /api/admin/interviews - List all interviews with admin metadata
export const GET = withAdminAuth(async (request: NextRequest) => {
  try {
    const interviews = await loadManifest();
    
    // Add admin metadata
    const adminInterviews = interviews.map(interview => ({
      ...interview,
      adminMetadata: {
        lastModified: interview.adminMetadata?.lastModified || new Date().toISOString(),
        modifiedBy: interview.adminMetadata?.modifiedBy || 'system',
        version: interview.adminMetadata?.version || 1,
      }
    }));
    
    return NextResponse.json({
      success: true,
      data: adminInterviews,
      count: adminInterviews.length,
    });
  } catch (error) {
    console.error('GET /api/admin/interviews error:', error);
    return NextResponse.json(
      { success: false, error: 'Failed to load interviews' },
      { status: 500 }
    );
  }
});

// POST /api/admin/interviews - Create new interview
export const POST = withAdminAuth(async (request: NextRequest) => {
  try {
    const body = await request.json();
    const validationErrors = validateInterviewData(body);
    
    if (validationErrors.length > 0) {
      return NextResponse.json(
        { success: false, errors: validationErrors },
        { status: 400 }
      );
    }
    
    const interviews = await loadManifest();
    
    // Generate new ID
    const maxId = Math.max(...interviews.map(i => parseInt(i.id) || 0), 0);
    const newId = (maxId + 1).toString();
    
    const newInterview: Interview = {
      id: newId,
      metadata: {
        interviewee: body.metadata.interviewee.trim(),
        summary: body.metadata.summary.trim(),
        date: body.metadata.date || new Date().toISOString().split('T')[0],
      },
      assets: body.assets || {
        video: '',
        subtitles: {},
      },
      transcripts: body.transcripts || [],
      adminMetadata: {
        lastModified: new Date().toISOString(),
        modifiedBy: getAuthenticatedUser(request).id,
        version: 1,
      }
    };
    
    interviews.push(newInterview);
    await saveManifest(interviews);
    
    return NextResponse.json({
      success: true,
      data: newInterview,
      message: 'Interview created successfully',
    }, { status: 201 });
    
  } catch (error) {
    console.error('POST /api/admin/interviews error:', error);
    return NextResponse.json(
      { success: false, error: 'Failed to create interview' },
      { status: 500 }
    );
  }
});
