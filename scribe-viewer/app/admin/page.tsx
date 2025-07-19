'use client';

import { useState, useEffect } from 'react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Loader2, RefreshCw, Edit, Trash2, Plus } from 'lucide-react';
import { Interview } from '@/lib/types';

export default function AdminPage() {
  const [interviews, setInterviews] = useState<Interview[]>([]);
  const [loading, setLoading] = useState(true);
  const [reindexing, setReindexing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Load interviews on component mount
  useEffect(() => {
    loadInterviews();
  }, []);

  const loadInterviews = async () => {
    try {
      setLoading(true);
      setError(null);
      const response = await fetch('/api/admin/interviews');
      const result = await response.json();
      
      if (result.success) {
        setInterviews(result.data);
      } else {
        setError(result.error || 'Failed to load interviews');
      }
    } catch (err) {
      setError('Network error loading interviews');
      console.error('Error loading interviews:', err);
    } finally {
      setLoading(false);
    }
  };

  const handleReindex = async () => {
    try {
      setReindexing(true);
      const response = await fetch('/api/admin/reindex', { method: 'POST' });
      const result = await response.json();
      
      if (result.success) {
        // Show success message or update UI
        console.log('Reindex successful:', result);
      } else {
        setError(result.error || 'Failed to reindex');
      }
    } catch (err) {
      setError('Network error during reindex');
      console.error('Error reindexing:', err);
    } finally {
      setReindexing(false);
    }
  };

  const handleDelete = async (id: string) => {
    if (!confirm('Are you sure you want to delete this interview?')) {
      return;
    }

    try {
      const response = await fetch(`/api/admin/interviews/${id}`, { 
        method: 'DELETE' 
      });
      const result = await response.json();
      
      if (result.success) {
        // Remove from local state
        setInterviews(prev => prev.filter(interview => interview.id !== id));
      } else {
        setError(result.error || 'Failed to delete interview');
      }
    } catch (err) {
      setError('Network error deleting interview');
      console.error('Error deleting interview:', err);
    }
  };

  if (loading) {
    return (
      <div className="container mx-auto px-4 py-8">
        <div className="flex items-center justify-center">
          <Loader2 className="h-8 w-8 animate-spin" />
          <span className="ml-2">Loading interviews...</span>
        </div>
      </div>
    );
  }

  return (
    <div className="container mx-auto px-4 py-8">
      <div className="flex justify-between items-center mb-6">
        <h1 className="text-3xl font-bold">Admin Panel</h1>
        <div className="flex gap-2">
          <Button onClick={loadInterviews} variant="outline">
            <RefreshCw className="h-4 w-4 mr-2" />
            Refresh
          </Button>
          <Button onClick={handleReindex} disabled={reindexing}>
            {reindexing ? (
              <Loader2 className="h-4 w-4 mr-2 animate-spin" />
            ) : (
              <RefreshCw className="h-4 w-4 mr-2" />
            )}
            Reindex Search
          </Button>
          <Button>
            <Plus className="h-4 w-4 mr-2" />
            Add Interview
          </Button>
        </div>
      </div>

      {error && (
        <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded mb-4">
          {error}
        </div>
      )}

      <div className="grid gap-4">
        <Card>
          <CardHeader>
            <CardTitle>Interview Management</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-sm text-muted-foreground mb-4">
              Total interviews: {interviews.length}
            </div>
            
            <div className="space-y-4">
              {interviews.map((interview) => (
                <div key={interview.id} className="flex items-center justify-between p-4 border rounded-lg">
                  <div className="flex-1">
                    <h3 className="font-semibold">{interview.metadata.interviewee}</h3>
                    <p className="text-sm text-muted-foreground mt-1">
                      {interview.metadata.summary || 'No summary available'}
                    </p>
                    <div className="flex items-center gap-2 mt-2">
                      <Badge variant="secondary">
                        ID: {interview.id.slice(0, 8)}...
                      </Badge>
                      {interview.metadata.date && (
                        <Badge variant="outline">
                          {interview.metadata.date}
                        </Badge>
                      )}
                      {interview.transcripts && interview.transcripts.length > 0 && (
                        <Badge variant="outline">
                          {interview.transcripts.length} transcript(s)
                        </Badge>
                      )}
                      {interview.adminMetadata && (
                        <Badge variant="outline">
                          v{interview.adminMetadata.version}
                        </Badge>
                      )}
                    </div>
                  </div>
                  
                  <div className="flex gap-2">
                    <Button variant="outline" size="sm">
                      <Edit className="h-4 w-4" />
                    </Button>
                    <Button 
                      variant="outline" 
                      size="sm" 
                      onClick={() => handleDelete(interview.id)}
                    >
                      <Trash2 className="h-4 w-4" />
                    </Button>
                  </div>
                </div>
              ))}
              
              {interviews.length === 0 && (
                <div className="text-center py-8 text-muted-foreground">
                  No interviews found. Add some interviews to get started.
                </div>
              )}
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
