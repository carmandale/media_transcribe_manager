import { NextRequest, NextResponse } from 'next/server'
import { promises as fs } from 'fs'
import path from 'path'

// Load manifest to get file mappings
async function getVideoPath(fileId: string): Promise<string | null> {
  try {
    // Use the minified manifest which is much smaller
    const manifestPath = path.join(process.cwd(), 'public', 'manifest.min.json')
    const manifestData = await fs.readFile(manifestPath, 'utf8')
    const manifest = JSON.parse(manifestData)
    
    const interview = manifest.find((item: any) => item.id === fileId)
    if (!interview || !interview.assets?.video) {
      return null
    }
    
    // Extract just the filename from the video path
    const videoPath = interview.assets.video
    const filename = videoPath.split('/').pop()
    
    // Construct the actual file path
    return path.join(process.cwd(), 'public', 'media', fileId, filename)
  } catch (error) {
    console.error('Error loading manifest:', error)
    return null
  }
}

export async function GET(
  request: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  try {
    const { id } = await params
    console.log('Video API - Requested ID:', id)
    
    // Get the actual file path from manifest
    const filePath = await getVideoPath(id)
    console.log('Video API - Resolved path:', filePath)
    
    if (!filePath) {
      console.error('Video API - No path found for ID:', id)
      return new NextResponse('Video not found', { status: 404 })
    }
    
    // Check if file exists
    try {
      await fs.access(filePath)
    } catch (error) {
      console.error('File not accessible:', filePath, error)
      return new NextResponse('File not found', { status: 404 })
    }
    
    // Get file stats
    const stat = await fs.stat(filePath)
    const fileSize = stat.size
    
    // Handle range requests for video streaming
    const range = request.headers.get('range')
    
    if (range) {
      // Parse range header
      const parts = range.replace(/bytes=/, '').split('-')
      const start = parseInt(parts[0], 10)
      const end = parts[1] ? parseInt(parts[1], 10) : fileSize - 1
      const chunksize = (end - start) + 1
      
      // Create read stream for the requested range
      const { createReadStream } = await import('fs')
      const stream = createReadStream(filePath, { start, end })
      
      // Convert stream to buffer
      const chunks: Buffer[] = []
      for await (const chunk of stream) {
        chunks.push(Buffer.from(chunk))
      }
      const buffer = Buffer.concat(chunks)
      
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
      const file = await fs.readFile(filePath)
      
      return new NextResponse(file, {
        headers: {
          'Content-Length': fileSize.toString(),
          'Content-Type': getContentType(filePath),
          'Accept-Ranges': 'bytes',
        },
      })
    }
  } catch (error) {
    console.error('Error serving video:', error)
    return new NextResponse('Internal server error', { status: 500 })
  }
}

function getContentType(filePath: string): string {
  const ext = path.extname(filePath).toLowerCase()
  
  const mimeTypes: { [key: string]: string } = {
    '.mp4': 'video/mp4',
    '.mp3': 'audio/mpeg',
    '.wav': 'audio/wav',
    '.m4a': 'audio/mp4',
  }
  
  return mimeTypes[ext] || 'application/octet-stream'
}