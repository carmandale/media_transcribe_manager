import { NextRequest, NextResponse } from 'next/server'
import { promises as fs } from 'fs'
import path from 'path'

export async function GET(
  request: NextRequest,
  { params }: { params: Promise<{ path: string[] }> }
) {
  try {
    // Await the params since they are a Promise in Next.js 15
    const { path: pathSegments } = await params
    
    // Reconstruct the file path from the URL segments
    // Next.js already URL-decodes the segments for us
    const filePath = pathSegments.join('/')
    
    console.log('Media API - Requested path:', filePath)
    
    // Construct the full path to the media file
    const fullPath = path.join(process.cwd(), 'public', 'media', filePath)
    
    // Check if file exists
    try {
      await fs.access(fullPath)
    } catch (error) {
      console.error('File not found:', fullPath)
      console.error('Error:', error)
      return new NextResponse(JSON.stringify({ 
        error: 'File not found', 
        requestedPath: filePath,
        fullPath: fullPath 
      }), { 
        status: 404,
        headers: { 'Content-Type': 'application/json' }
      })
    }
    
    // Get file stats
    const stat = await fs.stat(fullPath)
    const fileSize = stat.size
    
    // Handle range requests for video streaming
    const range = request.headers.get('range')
    
    if (range) {
      // Parse range header
      const parts = range.replace(/bytes=/, '').split('-')
      const start = parseInt(parts[0], 10)
      const end = parts[1] ? parseInt(parts[1], 10) : fileSize - 1
      const chunksize = (end - start) + 1
      
      // Read the requested chunk
      const fileHandle = await fs.open(fullPath, 'r')
      const buffer = Buffer.alloc(chunksize)
      await fileHandle.read(buffer, 0, chunksize, start)
      await fileHandle.close()
      
      // Return partial content
      return new NextResponse(buffer, {
        status: 206,
        headers: {
          'Content-Range': `bytes ${start}-${end}/${fileSize}`,
          'Accept-Ranges': 'bytes',
          'Content-Length': chunksize.toString(),
          'Content-Type': getContentType(filePath),
        },
      })
    } else {
      // Return entire file
      const file = await fs.readFile(fullPath)
      
      return new NextResponse(file, {
        headers: {
          'Content-Length': fileSize.toString(),
          'Content-Type': getContentType(filePath),
          'Accept-Ranges': 'bytes',
        },
      })
    }
  } catch (error) {
    console.error('Error serving media file:', error)
    return new NextResponse(JSON.stringify({ 
      error: 'Internal server error',
      message: error instanceof Error ? error.message : 'Unknown error'
    }), { 
      status: 500,
      headers: { 'Content-Type': 'application/json' }
    })
  }
}

function getContentType(filePath: string): string {
  const ext = path.extname(filePath).toLowerCase()
  
  const mimeTypes: { [key: string]: string } = {
    '.mp4': 'video/mp4',
    '.mp3': 'audio/mpeg',
    '.wav': 'audio/wav',
    '.m4a': 'audio/mp4',
    '.vtt': 'text/vtt',
    '.srt': 'text/plain',
  }
  
  return mimeTypes[ext] || 'application/octet-stream'
}