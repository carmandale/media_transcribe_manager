/**
 * Admin API route for search index management
 * Provides functionality to rebuild search indexes after data changes
 */

import { NextRequest, NextResponse } from 'next/server';
import { readFile } from 'fs/promises';
import { join } from 'path';
import { Interview } from '@/lib/types';
import { getSearchEngine } from '@/lib/search';
import { withAdminAuth } from '@/lib/auth';

const MANIFEST_PATH = join(process.cwd(), 'public', 'manifest.json');

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

// POST /api/admin/reindex - Rebuild search indexes
export const POST = withAdminAuth(async (request: NextRequest) => {
  try {
    const startTime = Date.now();
    
    // Load current manifest data
    const interviews = await loadManifest();
    
    if (interviews.length === 0) {
      return NextResponse.json({
        success: false,
        error: 'No interviews found to index',
      }, { status: 400 });
    }
    
    // Initialize search engine (this rebuilds the index)
    const searchEngine = getSearchEngine(interviews);
    
    // Get index statistics
    const filterOptions = searchEngine.getFilterOptions();
    const indexStats = {
      totalInterviews: interviews.length,
      totalTranscripts: interviews.reduce((sum, interview) => 
        sum + (interview.transcripts?.length || 0), 0
      ),
      languages: filterOptions.languages,
      interviewees: filterOptions.interviewees,
      dateRange: filterOptions.dateRange,
    };
    
    const endTime = Date.now();
    const duration = endTime - startTime;
    
    return NextResponse.json({
      success: true,
      message: 'Search index rebuilt successfully',
      stats: indexStats,
      performance: {
        duration: `${duration}ms`,
        indexedAt: new Date().toISOString(),
      }
    });
    
  } catch (error) {
    console.error('POST /api/admin/reindex error:', error);
    return NextResponse.json(
      { success: false, error: 'Failed to rebuild search index' },
      { status: 500 }
    );
  }
});

// GET /api/admin/reindex - Get current index status
export const GET = withAdminAuth(async (request: NextRequest) => {
  try {
    const interviews = await loadManifest();
    
    if (interviews.length === 0) {
      return NextResponse.json({
        success: true,
        status: 'empty',
        message: 'No interviews available for indexing',
        stats: {
          totalInterviews: 0,
          totalTranscripts: 0,
          languages: [],
          interviewees: [],
          dateRange: null,
        }
      });
    }
    
    // Get current search engine status
    const searchEngine = getSearchEngine(interviews);
    const filterOptions = searchEngine.getFilterOptions();
    
    const indexStats = {
      totalInterviews: interviews.length,
      totalTranscripts: interviews.reduce((sum, interview) => 
        sum + (interview.transcripts?.length || 0), 0
      ),
      languages: filterOptions.languages,
      interviewees: filterOptions.interviewees,
      dateRange: filterOptions.dateRange,
    };
    
    return NextResponse.json({
      success: true,
      status: 'ready',
      message: 'Search index is available',
      stats: indexStats,
      lastUpdated: new Date().toISOString(),
    });
    
  } catch (error) {
    console.error('GET /api/admin/reindex error:', error);
    return NextResponse.json(
      { success: false, error: 'Failed to get index status' },
      { status: 500 }
    );
  }
});
