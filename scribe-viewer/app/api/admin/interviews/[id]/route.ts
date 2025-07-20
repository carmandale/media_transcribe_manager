/**
 * Admin API routes for individual interview management
 * Provides GET, PUT, DELETE operations for specific interviews
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

// GET /api/admin/interviews/[id] - Get specific interview
export const GET = withAdminAuth(async (
  request: NextRequest,
  { params }: { params: { id: string } }
) => {
  try {
    const interviews = await loadManifest();
    const interview = interviews.find(i => i.id === params.id);
    
    if (!interview) {
      return NextResponse.json(
        { success: false, error: 'Interview not found' },
        { status: 404 }
      );
    }
    
    // Add admin metadata if missing
    const adminInterview = {
      ...interview,
      adminMetadata: {
        lastModified: interview.adminMetadata?.lastModified || new Date().toISOString(),
        modifiedBy: interview.adminMetadata?.modifiedBy || 'system',
        version: interview.adminMetadata?.version || 1,
      }
    };
    
    return NextResponse.json({
      success: true,
      data: adminInterview,
    });
  } catch (error) {
    console.error(`GET /api/admin/interviews/${params.id} error:`, error);
    return NextResponse.json(
      { success: false, error: 'Failed to load interview' },
      { status: 500 }
    );
  }
});

// PUT /api/admin/interviews/[id] - Update specific interview
export const PUT = withAdminAuth(async (
  request: NextRequest,
  { params }: { params: { id: string } }
) => {
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
    const interviewIndex = interviews.findIndex(i => i.id === params.id);
    
    if (interviewIndex === -1) {
      return NextResponse.json(
        { success: false, error: 'Interview not found' },
        { status: 404 }
      );
    }
    
    const existingInterview = interviews[interviewIndex];
    
    // Update interview with new data
    const updatedInterview: Interview = {
      ...existingInterview,
      metadata: {
        ...existingInterview.metadata,
        ...body.metadata,
        interviewee: body.metadata?.interviewee?.trim() || existingInterview.metadata.interviewee,
        summary: body.metadata?.summary?.trim() || existingInterview.metadata.summary,
      },
      assets: body.assets || existingInterview.assets,
      transcripts: body.transcripts || existingInterview.transcripts,
      adminMetadata: {
        lastModified: new Date().toISOString(),
        modifiedBy: getAuthenticatedUser(request).id,
        version: (existingInterview.adminMetadata?.version || 1) + 1,
      }
    };
    
    interviews[interviewIndex] = updatedInterview;
    await saveManifest(interviews);
    
    return NextResponse.json({
      success: true,
      data: updatedInterview,
      message: 'Interview updated successfully',
    });
    
  } catch (error) {
    console.error(`PUT /api/admin/interviews/${params.id} error:`, error);
    return NextResponse.json(
      { success: false, error: 'Failed to update interview' },
      { status: 500 }
    );
  }
});

// DELETE /api/admin/interviews/[id] - Delete specific interview
export const DELETE = withAdminAuth(async (
  request: NextRequest,
  { params }: { params: { id: string } }
) => {
  try {
    const interviews = await loadManifest();
    const interviewIndex = interviews.findIndex(i => i.id === params.id);
    
    if (interviewIndex === -1) {
      return NextResponse.json(
        { success: false, error: 'Interview not found' },
        { status: 404 }
      );
    }
    
    const deletedInterview = interviews[interviewIndex];
    interviews.splice(interviewIndex, 1);
    
    await saveManifest(interviews);
    
    return NextResponse.json({
      success: true,
      data: deletedInterview,
      message: 'Interview deleted successfully',
    });
    
  } catch (error) {
    console.error(`DELETE /api/admin/interviews/${params.id} error:`, error);
    return NextResponse.json(
      { success: false, error: 'Failed to delete interview' },
      { status: 500 }
    );
  }
});
