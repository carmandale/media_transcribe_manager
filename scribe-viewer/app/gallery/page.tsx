import { promises as fs } from 'fs'
import path from 'path'
import { Interview } from "@/lib/types"
import InterviewCard from "@/components/InterviewCard"
import GalleryClient from "@/app/gallery/gallery-client"

async function loadManifest(): Promise<Interview[]> {
  const minPath = path.join(process.cwd(), 'public', 'manifest.min.json')
  const fullPath = path.join(process.cwd(), 'public', 'manifest.json')

  // Try minified first, then fall back to full manifest
  try {
    const fileContents = await fs.readFile(minPath, 'utf8')
    const trimmed = fileContents.trim()
    const looksLikeJSON = trimmed.startsWith('{') || trimmed.startsWith('[')
    if (looksLikeJSON) {
      return JSON.parse(fileContents)
    }
  } catch (error) {
    console.error('Error loading manifest.min.json:', error)
  }

  try {
    const fileContents = await fs.readFile(fullPath, 'utf8')
    return JSON.parse(fileContents)
  } catch (error) {
    console.error('Error loading manifest.json:', error)
  }

  return []
}

export default async function GalleryPage() {
  const interviews = await loadManifest()
  
  return <GalleryClient interviews={interviews} />
}