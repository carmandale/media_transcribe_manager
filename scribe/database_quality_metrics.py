#!/usr/bin/env python3
"""
Database-Backed Quality Metrics for SRTTranslator Integration
--------------------------------------------------------------
This module implements Task 4.4: Enhance existing quality framework with database-backed metrics.
It extends the database schema to store comprehensive quality metrics for subtitle translations,
building upon the existing SRTTranslator quality validation mechanisms.

This is part of the subtitle-first architecture that ensures quality metrics are
persisted and trackable across the entire subtitle translation workflow.
"""

import logging
from typing import Dict, Any, List, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


def add_quality_metrics_schema(db):
    """
    Add quality metrics table to database schema for enhanced quality tracking.
    
    This extends the existing database schema with comprehensive quality metrics
    storage, building upon the proven SRTTranslator validation framework.
    
    Args:
        db: Database instance to extend
    """
    with db.transaction() as conn:
        # Check if quality metrics table already exists
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='subtitle_quality_metrics'"
        )
        if cursor.fetchone() is not None:
            logger.debug("subtitle_quality_metrics table already exists")
            return
        
        logger.info("Creating enhanced subtitle quality metrics tables...")
        
        # Create comprehensive quality metrics table
        conn.execute("""
            CREATE TABLE subtitle_quality_metrics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                interview_id TEXT NOT NULL,
                language TEXT NOT NULL,
                metric_type TEXT NOT NULL,
                metric_value REAL NOT NULL,
                metric_details TEXT,
                evaluation_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                evaluation_method TEXT,
                FOREIGN KEY (interview_id) REFERENCES media_files(file_id),
                UNIQUE(interview_id, language, metric_type)
            )
        """)
        
        # Create segment-level quality scores table
        conn.execute("""
            CREATE TABLE segment_quality_scores (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                interview_id TEXT NOT NULL,
                segment_index INTEGER NOT NULL,
                language TEXT NOT NULL,
                timing_accuracy_score REAL,
                translation_quality_score REAL,
                synchronization_score REAL,
                boundary_preservation_score REAL,
                overall_score REAL,
                evaluation_details TEXT,
                evaluated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (interview_id) REFERENCES media_files(file_id),
                UNIQUE(interview_id, segment_index, language)
            )
        """)
        
        # Create timing coordination metrics table
        conn.execute("""
            CREATE TABLE timing_coordination_metrics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                interview_id TEXT NOT NULL,
                language TEXT NOT NULL,
                total_segments INTEGER NOT NULL,
                perfect_boundaries INTEGER DEFAULT 0,
                timing_gaps INTEGER DEFAULT 0,
                timing_overlaps INTEGER DEFAULT 0,
                max_gap_duration REAL DEFAULT 0,
                max_overlap_duration REAL DEFAULT 0,
                avg_segment_duration REAL,
                timing_drift_ms REAL DEFAULT 0,
                srt_compatibility_score REAL,
                evaluated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (interview_id) REFERENCES media_files(file_id),
                UNIQUE(interview_id, language)
            )
        """)
        
        # Create indexes for performance
        conn.execute("CREATE INDEX idx_quality_metrics_interview ON subtitle_quality_metrics(interview_id)")
        conn.execute("CREATE INDEX idx_quality_metrics_language ON subtitle_quality_metrics(interview_id, language)")
        conn.execute("CREATE INDEX idx_segment_scores_interview ON segment_quality_scores(interview_id)")
        conn.execute("CREATE INDEX idx_timing_metrics_interview ON timing_coordination_metrics(interview_id)")
        
        # Create aggregate quality view
        conn.execute("""
            CREATE VIEW interview_quality_summary AS
            SELECT 
                sqm.interview_id,
                sqm.language,
                AVG(CASE WHEN sqm.metric_type = 'overall_quality' THEN sqm.metric_value END) as overall_quality_score,
                AVG(CASE WHEN sqm.metric_type = 'translation_accuracy' THEN sqm.metric_value END) as translation_accuracy,
                AVG(CASE WHEN sqm.metric_type = 'timing_precision' THEN sqm.metric_value END) as timing_precision,
                AVG(CASE WHEN sqm.metric_type = 'boundary_validation' THEN sqm.metric_value END) as boundary_validation,
                COUNT(DISTINCT sqs.segment_index) as evaluated_segments,
                AVG(sqs.overall_score) as avg_segment_score,
                tcm.srt_compatibility_score,
                tcm.perfect_boundaries,
                tcm.timing_gaps,
                tcm.timing_overlaps,
                MAX(sqm.evaluation_timestamp) as last_evaluated
            FROM subtitle_quality_metrics sqm
            LEFT JOIN segment_quality_scores sqs ON sqm.interview_id = sqs.interview_id AND sqm.language = sqs.language
            LEFT JOIN timing_coordination_metrics tcm ON sqm.interview_id = tcm.interview_id AND sqm.language = tcm.language
            GROUP BY sqm.interview_id, sqm.language
        """)
        
        logger.info("Enhanced quality metrics schema created successfully")


def store_quality_metrics(db, interview_id: str, language: str, metrics: Dict[str, Any]) -> bool:
    """
    Store quality metrics in database for persistent tracking.
    
    This implements the database storage for quality metrics, building upon
    the existing SRTTranslator validation results.
    
    Args:
        db: Database instance
        interview_id: ID of the interview
        language: Language code ('en', 'de', 'he')
        metrics: Dictionary of quality metrics to store
        
    Returns:
        True if metrics stored successfully
    """
    try:
        with db.transaction() as conn:
            # Store overall metrics
            for metric_type, metric_value in metrics.items():
                if isinstance(metric_value, (int, float)):
                    conn.execute("""
                        INSERT OR REPLACE INTO subtitle_quality_metrics
                        (interview_id, language, metric_type, metric_value, evaluation_method)
                        VALUES (?, ?, ?, ?, ?)
                    """, (
                        interview_id,
                        language,
                        metric_type,
                        metric_value,
                        metrics.get('evaluation_method', 'enhanced_database_validation')
                    ))
            
            logger.info(f"Stored {len(metrics)} quality metrics for {interview_id} in {language}")
            return True
            
    except Exception as e:
        logger.error(f"Failed to store quality metrics: {e}")
        return False


def store_segment_quality_scores(db, interview_id: str, language: str, 
                               segment_scores: List[Dict[str, Any]]) -> bool:
    """
    Store segment-level quality scores for detailed tracking.
    
    Args:
        db: Database instance
        interview_id: ID of the interview
        language: Language code
        segment_scores: List of segment score dictionaries
        
    Returns:
        True if scores stored successfully
    """
    try:
        with db.transaction() as conn:
            for score in segment_scores:
                conn.execute("""
                    INSERT OR REPLACE INTO segment_quality_scores
                    (interview_id, segment_index, language, 
                     timing_accuracy_score, translation_quality_score,
                     synchronization_score, boundary_preservation_score,
                     overall_score, evaluation_details)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    interview_id,
                    score['segment_index'],
                    language,
                    score.get('timing_accuracy_score'),
                    score.get('translation_quality_score'),
                    score.get('synchronization_score'),
                    score.get('boundary_preservation_score'),
                    score.get('overall_score'),
                    score.get('evaluation_details')
                ))
            
            logger.info(f"Stored quality scores for {len(segment_scores)} segments")
            return True
            
    except Exception as e:
        logger.error(f"Failed to store segment quality scores: {e}")
        return False


def store_timing_coordination_metrics(db, interview_id: str, language: str,
                                    timing_metrics: Dict[str, Any]) -> bool:
    """
    Store timing coordination metrics from SRTTranslator validation.
    
    This captures the proven timing validation results from SRTTranslator
    and persists them for tracking and analysis.
    
    Args:
        db: Database instance
        interview_id: ID of the interview
        language: Language code
        timing_metrics: Timing validation results
        
    Returns:
        True if metrics stored successfully
    """
    try:
        with db.transaction() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO timing_coordination_metrics
                (interview_id, language, total_segments, perfect_boundaries,
                 timing_gaps, timing_overlaps, max_gap_duration, max_overlap_duration,
                 avg_segment_duration, timing_drift_ms, srt_compatibility_score)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                interview_id,
                language,
                timing_metrics.get('total_segments', 0),
                timing_metrics.get('perfect_boundaries', 0),
                timing_metrics.get('timing_gaps', 0),
                timing_metrics.get('timing_overlaps', 0),
                timing_metrics.get('max_gap_duration', 0),
                timing_metrics.get('max_overlap_duration', 0),
                timing_metrics.get('avg_segment_duration', 0),
                timing_metrics.get('timing_drift_ms', 0),
                timing_metrics.get('srt_compatibility_score', 0)
            ))
            
            logger.info(f"Stored timing coordination metrics for {interview_id} in {language}")
            return True
            
    except Exception as e:
        logger.error(f"Failed to store timing metrics: {e}")
        return False


def get_quality_metrics(db, interview_id: str, language: Optional[str] = None) -> Dict[str, Any]:
    """
    Retrieve quality metrics from database.
    
    Args:
        db: Database instance
        interview_id: ID of the interview
        language: Optional language filter
        
    Returns:
        Dictionary of quality metrics
    """
    conn = db._get_connection()
    
    if language:
        cursor = conn.execute("""
            SELECT * FROM interview_quality_summary
            WHERE interview_id = ? AND language = ?
        """, (interview_id, language))
    else:
        cursor = conn.execute("""
            SELECT * FROM interview_quality_summary
            WHERE interview_id = ?
        """, (interview_id,))
    
    results = []
    for row in cursor.fetchall():
        try:
            results.append(dict(row))
        except (TypeError, ValueError):
            continue
    
    return results[0] if results and language else results


def get_segment_quality_history(db, interview_id: str, language: str, 
                              segment_index: Optional[int] = None) -> List[Dict[str, Any]]:
    """
    Get quality score history for segments.
    
    Args:
        db: Database instance
        interview_id: ID of the interview
        language: Language code
        segment_index: Optional specific segment
        
    Returns:
        List of quality score records
    """
    conn = db._get_connection()
    
    if segment_index is not None:
        cursor = conn.execute("""
            SELECT * FROM segment_quality_scores
            WHERE interview_id = ? AND language = ? AND segment_index = ?
            ORDER BY evaluated_at DESC
        """, (interview_id, language, segment_index))
    else:
        cursor = conn.execute("""
            SELECT * FROM segment_quality_scores
            WHERE interview_id = ? AND language = ?
            ORDER BY segment_index, evaluated_at DESC
        """, (interview_id, language))
    
    results = []
    for row in cursor.fetchall():
        try:
            results.append(dict(row))
        except (TypeError, ValueError):
            continue
    
    return results


def calculate_quality_trends(db, interview_id: str) -> Dict[str, Any]:
    """
    Calculate quality trends across languages and time.
    
    Args:
        db: Database instance
        interview_id: ID of the interview
        
    Returns:
        Dictionary with quality trend analysis
    """
    conn = db._get_connection()
    
    # Get quality metrics over time
    cursor = conn.execute("""
        SELECT 
            language,
            metric_type,
            metric_value,
            evaluation_timestamp
        FROM subtitle_quality_metrics
        WHERE interview_id = ?
        ORDER BY evaluation_timestamp
    """, (interview_id,))
    
    trends = {
        'languages': {},
        'overall_trend': 'stable',
        'quality_improvements': [],
        'quality_degradations': []
    }
    
    for row in cursor.fetchall():
        lang = row['language']
        if lang not in trends['languages']:
            trends['languages'][lang] = {
                'metrics': {},
                'trend': 'stable',
                'latest_score': 0
            }
        
        metric_type = row['metric_type']
        if metric_type not in trends['languages'][lang]['metrics']:
            trends['languages'][lang]['metrics'][metric_type] = []
        
        trends['languages'][lang]['metrics'][metric_type].append({
            'value': row['metric_value'],
            'timestamp': row['evaluation_timestamp']
        })
    
    # Analyze trends
    for lang, data in trends['languages'].items():
        for metric_type, values in data['metrics'].items():
            if len(values) > 1:
                first_value = values[0]['value']
                last_value = values[-1]['value']
                change = last_value - first_value
                
                if change > 0.1:  # Significant improvement
                    trends['quality_improvements'].append({
                        'language': lang,
                        'metric': metric_type,
                        'improvement': change
                    })
                elif change < -0.1:  # Significant degradation
                    trends['quality_degradations'].append({
                        'language': lang,
                        'metric': metric_type,
                        'degradation': abs(change)
                    })
        
        # Set latest score
        if 'overall_quality' in data['metrics'] and data['metrics']['overall_quality']:
            data['latest_score'] = data['metrics']['overall_quality'][-1]['value']
    
    # Determine overall trend
    if len(trends['quality_improvements']) > len(trends['quality_degradations']):
        trends['overall_trend'] = 'improving'
    elif len(trends['quality_degradations']) > len(trends['quality_improvements']):
        trends['overall_trend'] = 'degrading'
    
    return trends


# Integration with DatabaseTranslator enhanced methods
def enhance_database_translator_with_metrics(DatabaseTranslator):
    """
    Enhance DatabaseTranslator class with quality metrics methods.
    
    This is a mixin approach to add quality metrics functionality
    to the existing DatabaseTranslator class.
    """
    
    def store_translation_quality_metrics(self, interview_id: str, language: str,
                                        validation_results: Dict[str, Any]) -> bool:
        """
        Store quality metrics from translation validation results.
        
        This method bridges the existing validation results with the new
        database-backed metrics storage.
        """
        try:
            # Extract metrics from validation results
            metrics = {
                'overall_quality': validation_results.get('quality_scores', {}).get('average_quality', 0),
                'translation_accuracy': 0,
                'timing_precision': 0,
                'boundary_validation': 1.0 if validation_results.get('valid', False) else 0.0,
                'evaluation_method': validation_results.get('validation_method', 'enhanced_database_validation')
            }
            
            # Calculate translation accuracy from quality scores
            if 'quality_scores' in validation_results:
                quality_scores = validation_results['quality_scores']
                if isinstance(quality_scores, dict):
                    segment_scores = []
                    for key, value in quality_scores.items():
                        if key.startswith('segment_') and key.endswith('_comprehensive'):
                            if isinstance(value, dict) and 'score' in value:
                                segment_scores.append(value['score'])
                    
                    if segment_scores:
                        metrics['translation_accuracy'] = sum(segment_scores) / len(segment_scores) / 10.0
            
            # Store metrics
            return store_quality_metrics(self.db, interview_id, language, metrics)
            
        except Exception as e:
            logger.error(f"Failed to store translation quality metrics: {e}")
            return False
    
    def calculate_timing_accuracy_metrics(self, interview_id: str, language: str,
                                        timing_validation: Dict[str, Any]) -> Dict[str, Any]:
        """
        Calculate and store detailed timing accuracy metrics.
        
        This builds upon the existing timing validation results from
        SRTTranslator integration.
        """
        try:
            # Extract timing metrics from validation
            db_validation = timing_validation.get('database_validation_details', {})
            timing_issues = timing_validation.get('timing_issues', [])
            
            # Calculate timing gaps and overlaps
            gaps = []
            overlaps = []
            for issue in timing_issues:
                if 'gap' in issue.lower():
                    # Extract gap duration from issue string
                    import re
                    match = re.search(r'gap of ([\d.]+)s', issue.lower())
                    if match:
                        gaps.append(float(match.group(1)))
                elif 'overlap' in issue.lower():
                    # Extract overlap duration
                    match = re.search(r'overlap of ([\d.]+)s', issue.lower())
                    if match:
                        overlaps.append(float(match.group(1)))
            
            timing_metrics = {
                'total_segments': timing_validation.get('segment_count', 0),
                'perfect_boundaries': timing_validation.get('segment_count', 0) - len(timing_issues),
                'timing_gaps': len(gaps),
                'timing_overlaps': len(overlaps),
                'max_gap_duration': max(gaps) if gaps else 0,
                'max_overlap_duration': max(overlaps) if overlaps else 0,
                'avg_segment_duration': timing_validation.get('total_duration', 0) / max(timing_validation.get('segment_count', 1), 1),
                'timing_drift_ms': 0,  # Calculate if segments drift from expected timing
                'srt_compatibility_score': 1.0 if timing_validation.get('srt_compatibility', False) else 0.0
            }
            
            # Store timing metrics
            store_timing_coordination_metrics(self.db, interview_id, language, timing_metrics)
            
            return timing_metrics
            
        except Exception as e:
            logger.error(f"Failed to calculate timing accuracy metrics: {e}")
            return {}
    
    def get_comprehensive_quality_report(self, interview_id: str) -> Dict[str, Any]:
        """
        Generate comprehensive quality report using stored metrics.
        
        This provides a complete quality assessment across all languages
        and aspects of the translation.
        """
        report = {
            'interview_id': interview_id,
            'languages': {},
            'overall_quality': 0,
            'timing_coordination': {},
            'quality_trends': {},
            'recommendations': []
        }
        
        try:
            # Get metrics for all languages
            for lang in ['en', 'de', 'he']:
                lang_metrics = get_quality_metrics(self.db, interview_id, lang)
                if lang_metrics:
                    report['languages'][lang] = lang_metrics
            
            # Calculate overall quality
            quality_scores = []
            for lang_data in report['languages'].values():
                if 'overall_quality_score' in lang_data and lang_data['overall_quality_score']:
                    quality_scores.append(lang_data['overall_quality_score'])
            
            if quality_scores:
                report['overall_quality'] = sum(quality_scores) / len(quality_scores)
            
            # Get quality trends
            report['quality_trends'] = calculate_quality_trends(self.db, interview_id)
            
            # Generate recommendations
            if report['overall_quality'] < 7.0:
                report['recommendations'].append("Consider re-evaluating translations with lower quality scores")
            
            for lang, data in report['languages'].items():
                if data.get('timing_gaps', 0) > 5:
                    report['recommendations'].append(f"Review timing gaps in {lang} translation")
                if data.get('timing_overlaps', 0) > 0:
                    report['recommendations'].append(f"Fix timing overlaps in {lang} translation")
            
            return report
            
        except Exception as e:
            logger.error(f"Failed to generate quality report: {e}")
            report['error'] = str(e)
            return report
    
    # Add methods to DatabaseTranslator class
    DatabaseTranslator.store_translation_quality_metrics = store_translation_quality_metrics
    DatabaseTranslator.calculate_timing_accuracy_metrics = calculate_timing_accuracy_metrics
    DatabaseTranslator.get_comprehensive_quality_report = get_comprehensive_quality_report
    
    return DatabaseTranslator