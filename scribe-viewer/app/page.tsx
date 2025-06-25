"use client"

import { useState } from "react"
import { Button } from "@/components/ui/button"
import { Moon, Sun } from "lucide-react"
import { ThemeProvider } from "@/components/theme-provider"
import GalleryPage from "../gallery-page"
import SearchResultsPage from "../search-results-page"
import ViewerPage from "../viewer-page"
import AdminPage from "../admin-page"

const pages = [
  { id: "gallery", name: "Gallery (Homepage)", component: GalleryPage },
  { id: "search", name: "Search Results", component: SearchResultsPage },
  { id: "viewer", name: "Video Viewer", component: ViewerPage },
  { id: "admin", name: "Admin Dashboard", component: AdminPage },
]

function AppContent() {
  const [currentPage, setCurrentPage] = useState("gallery")
  const [isDark, setIsDark] = useState(true)

  const CurrentComponent = pages.find((p) => p.id === currentPage)?.component || GalleryPage

  // Apply dark mode to document
  if (typeof document !== "undefined") {
    if (isDark) {
      document.documentElement.classList.add("dark")
    } else {
      document.documentElement.classList.remove("dark")
    }
  }

  return (
    <div className="min-h-screen bg-background text-foreground">
      {/* Navigation Bar */}
      <nav className="bg-background border-b border-border shadow-sm sticky top-0 z-50">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center justify-between h-16">
            <div className="flex items-center gap-4">
              <h1 className="text-xl font-bold">Scribe Viewer Mockups</h1>
              <div className="hidden md:flex items-center gap-2">
                {pages.map((page) => (
                  <Button
                    key={page.id}
                    variant={currentPage === page.id ? "default" : "ghost"}
                    size="sm"
                    onClick={() => setCurrentPage(page.id)}
                  >
                    {page.name}
                  </Button>
                ))}
              </div>
            </div>

            <div className="flex items-center gap-2">
              {/* Mobile dropdown for smaller screens */}
              <div className="md:hidden">
                <select
                  value={currentPage}
                  onChange={(e) => setCurrentPage(e.target.value)}
                  className="border border-border rounded px-3 py-1 bg-background"
                >
                  {pages.map((page) => (
                    <option key={page.id} value={page.id}>
                      {page.name}
                    </option>
                  ))}
                </select>
              </div>

              {/* Dark mode toggle */}
              <Button variant="ghost" size="sm" onClick={() => setIsDark(!isDark)}>
                {isDark ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
              </Button>
            </div>
          </div>
        </div>
      </nav>

      {/* Current Page Content */}
      <CurrentComponent />
    </div>
  )
}

export default function Page() {
  return (
    <ThemeProvider attribute="class" defaultTheme="dark" enableSystem>
      <AppContent />
    </ThemeProvider>
  )
}
