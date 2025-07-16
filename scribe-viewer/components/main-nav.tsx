"use client"

import { useState } from "react"
import Link from "next/link"
import { usePathname } from "next/navigation"
import { Button } from "@/components/ui/button"
import { Moon, Sun } from "lucide-react"
import { useTheme } from "next-themes"

const pages = [
  { href: "/gallery", name: "Gallery" },
  { href: "/admin", name: "Admin" },
]

export function MainNav() {
  const pathname = usePathname()
  const { setTheme, theme } = useTheme()

  return (
    <nav className="bg-background border-b border-border shadow-sm sticky top-0 z-50">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex items-center justify-between h-16">
          <div className="flex items-center gap-4">
            <Link href="/gallery" className="text-xl font-bold">
              Scribe Viewer
            </Link>
            <div className="hidden md:flex items-center gap-2">
              {pages.map((page) => (
                <Link key={page.name} href={page.href} legacyBehavior passHref>
                  <Button
                    variant={pathname === page.href ? "default" : "ghost"}
                    size="sm"
                  >
                    {page.name}
                  </Button>
                </Link>
              ))}
            </div>
          </div>

          <div className="flex items-center gap-2">
            <div className="md:hidden">
              <select
                value={pathname}
                onChange={(e) => {
                  // This is a simple example; for full SPA-like behavior,
                  // you might use Next.js's router.push()
                  window.location.href = e.target.value;
                }}
                className="border border-border rounded px-3 py-1 bg-background"
              >
                {pages.map((page) => (
                  <option key={page.href} value={page.href}>
                    {page.name}
                  </option>
                ))}
              </select>
            </div>
            <Button
              variant="ghost"
              size="sm"
              onClick={() => setTheme(theme === "dark" ? "light" : "dark")}
            >
              <Sun className="h-4 w-4 rotate-0 scale-100 transition-all dark:-rotate-90 dark:scale-0" />
              <Moon className="absolute h-4 w-4 rotate-90 scale-0 transition-all dark:rotate-0 dark:scale-100" />
              <span className="sr-only">Toggle theme</span>
            </Button>
          </div>
        </div>
      </div>
    </nav>
  )
} 