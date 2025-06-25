#!/usr/bin/env python3
"""
German Translation Improvement System
Systematically re-translates and improves German translations focusing on historical accuracy.
"""

import asyncio
import json
import logging
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional

# Add the parent directory to Python path for imports
sys.path.append(str(Path(__file__).parent.parent))

from scribe.database import Database
from scribe.pipeline import Pipeline
from scribe.evaluate import HistoricalEvaluator
from scribe.translate import translate_text
from scribe.utils import load_api_key, setup_logging

# Set up logging
logger = logging.getLogger(__name__)

class GermanImprovementPipeline:
    """Enhanced German translation pipeline focused on quality improvement."""
    
    # Enhanced German translation prompt for historical accuracy
    ENHANCED_GERMAN_PROMPT = """
Du bist ein Experte für deutsche Übersetzungen historischer Interviews und Zeitzeugenberichte. 
Übersetze das folgende Interview-Transkript ins Deutsche und beachte dabei:

KERNPRINZIPIEN:
1. HISTORISCHE GENAUIGKEIT: Bewahre alle Namen, Daten, Orte und historische Details exakt
2. SPRECHWEISE ERHALTEN: Behalte die natürliche Sprechweise, Zögerungen und emotionale Nuancen bei
3. KULTURELLER KONTEXT: Verwende angemessene deutsche Begriffe für historische Konzepte
4. AUTHENTIZITÄT: Die Übersetzung muss für historische Forschung und Archivierung geeignet sein

SPEZIELLE ANWEISUNGEN:
- Übersetze Namen und Orte nicht, sondern übernimm sie originalgetreu
- Bewahre Zeitangaben und Daten exakt (z.B. "1938" bleibt "1938")
- Verwende angemessene deutsche Begriffe für historische Begriffe (z.B. "Wehrmacht", "Gestapo")
- Behalte die emotionale Intensität und den Ton des Originals bei
- Übersetze direkte Rede in natürliches, gesprochenes Deutsch
- Bewahre Pausen, Zögerungen und umgangssprachliche Elemente

Das zu übersetzende Interview:

{text}

Antworte NUR mit der deutschen Übersetzung, ohne Erklärungen oder Zusätze.
"""

    def __init__(self):
        """Initialize the improvement pipeline."""
        self.db = Database()
        self.pipeline = Pipeline()
        self.evaluator = HistoricalEvaluator()
        
    async def find_improvement_candidates(self, min_score: float = 7.0, sample_size: int = 50) -> List[Dict]:
        """
        Find German files that need improvement by sampling and evaluating.
        
        Args:
            min_score: Minimum acceptable score
            sample_size: Number of files to evaluate for sampling
            
        Returns:
            List of file info for files needing improvement
        """
        logger.info(f"Sampling {sample_size} German files for quality assessment...")
        
        # Get completed German translations
        completed_files = self.db.execute_query('''
            SELECT m.file_id, m.safe_filename, m.original_path
            FROM media_files m
            JOIN processing_status p ON m.file_id = p.file_id
            WHERE p.translation_de_status = 'completed'
            ORDER BY RANDOM()
            LIMIT ?
        ''', (sample_size,))
        
        improvement_candidates = []
        
        for file_info in completed_files:
            try:
                # Get file paths
                file_id = file_info['file_id']
                output_dir = Path("output") / file_id
                
                original_file = output_dir / f"{file_id}.txt"
                german_file = output_dir / f"{file_id}.de.txt"
                
                if not original_file.exists() or not german_file.exists():
                    continue
                
                # Read texts
                with open(original_file, 'r', encoding='utf-8') as f:
                    original_text = f.read()[:3000]  # Limit for evaluation
                
                with open(german_file, 'r', encoding='utf-8') as f:
                    german_text = f.read()[:3000]
                
                # Evaluate current translation
                result = self.evaluator.evaluate(original_text, german_text, language="de")
                
                if result:
                    score = result.get('composite_score', 0)
                    logger.info(f"Evaluated {file_id}: {score:.1f}/10")
                    
                    if score < min_score:
                        improvement_candidates.append({
                            'file_id': file_id,
                            'current_score': score,
                            'safe_filename': file_info['safe_filename'],
                            'evaluation_details': result
                        })
                
                # Rate limiting
                await asyncio.sleep(1)
                
            except Exception as e:
                logger.error(f"Error evaluating {file_id}: {e}")
                continue
        
        logger.info(f"Found {len(improvement_candidates)} files needing improvement")
        return improvement_candidates
    
    async def improve_translation(self, file_id: str, api_key: str) -> Optional[Dict]:
        """
        Improve a single German translation.
        
        Args:
            file_id: File ID to improve
            api_key: OpenAI API key
            
        Returns:
            Improvement result with before/after scores
        """
        output_dir = Path("output") / file_id
        original_file = output_dir / f"{file_id}.txt"
        german_file = output_dir / f"{file_id}.de.txt"
        backup_file = output_dir / f"{file_id}.de.backup.txt"
        
        if not original_file.exists() or not german_file.exists():
            logger.error(f"Files not found for {file_id}")
            return None
        
        try:
            # Read original text
            with open(original_file, 'r', encoding='utf-8') as f:
                original_text = f.read()
            
            # Read current German translation
            with open(german_file, 'r', encoding='utf-8') as f:
                current_german = f.read()
            
            # Evaluate current translation
            current_result = self.evaluator.evaluate(
                original_text[:3000], 
                current_german[:3000], 
                language="de"
            )
            current_score = current_result.get('composite_score', 0) if current_result else 0
            
            logger.info(f"Current score for {file_id}: {current_score:.1f}/10")
            
            # If already good, skip improvement
            if current_score >= 7.5:
                logger.info(f"File {file_id} already has good score, skipping")
                return {
                    'file_id': file_id,
                    'improved': False,
                    'reason': 'already_good',
                    'current_score': current_score
                }
            
            # Create backup
            with open(backup_file, 'w', encoding='utf-8') as f:
                f.write(current_german)
            
            # Generate improved translation using enhanced prompt
            improved_german = translate_text(
                text=original_text,
                target_language="de", 
                source_language="en",
                config={'custom_prompt': self.ENHANCED_GERMAN_PROMPT}
            )
            
            if not improved_german:
                logger.error(f"Failed to generate improved translation for {file_id}")
                return None
            
            # Evaluate improved translation
            improved_result = self.evaluator.evaluate(
                original_text[:3000], 
                improved_german[:3000], 
                language="de"
            )
            improved_score = improved_result.get('composite_score', 0) if improved_result else 0
            
            logger.info(f"Improved score for {file_id}: {improved_score:.1f}/10")
            
            # Only keep improvement if it's actually better
            if improved_score > current_score + 0.5:  # Require significant improvement
                # Save improved translation
                with open(german_file, 'w', encoding='utf-8') as f:
                    f.write(improved_german)
                
                logger.info(f"✅ Improved {file_id}: {current_score:.1f} → {improved_score:.1f}")
                
                return {
                    'file_id': file_id,
                    'improved': True,
                    'before_score': current_score,
                    'after_score': improved_score,
                    'improvement': improved_score - current_score,
                    'before_evaluation': current_result,
                    'after_evaluation': improved_result
                }
            else:
                # Revert to original if no improvement
                with open(german_file, 'w', encoding='utf-8') as f:
                    f.write(current_german)
                
                logger.info(f"❌ No improvement for {file_id}: {current_score:.1f} → {improved_score:.1f}")
                
                return {
                    'file_id': file_id,
                    'improved': False,
                    'reason': 'no_improvement',
                    'before_score': current_score,
                    'attempted_score': improved_score
                }
                
        except Exception as e:
            logger.error(f"Error improving {file_id}: {e}")
            return None
    
    async def batch_improve(self, max_files: int = 100, min_score: float = 7.0) -> Dict:
        """
        Improve a batch of German translations.
        
        Args:
            max_files: Maximum number of files to improve
            min_score: Minimum acceptable score
            
        Returns:
            Summary of improvements made
        """
        api_key = load_api_key('OPENAI_API_KEY')
        if not api_key:
            logger.error("OpenAI API key not found")
            return {}
        
        # Find candidates for improvement
        candidates = await self.find_improvement_candidates(
            min_score=min_score, 
            sample_size=max_files * 2  # Sample more to find enough candidates
        )
        
        if not candidates:
            logger.info("No candidates found for improvement")
            return {'improved': 0, 'total_attempted': 0}
        
        # Sort by lowest score first (worst translations get priority)
        candidates = sorted(candidates, key=lambda x: x['current_score'])[:max_files]
        
        logger.info(f"Improving {len(candidates)} German translations...")
        
        results = {
            'improved': 0,
            'total_attempted': len(candidates),
            'improvements': [],
            'failed': [],
            'no_improvement': []
        }
        
        for i, candidate in enumerate(candidates, 1):
            logger.info(f"Processing {i}/{len(candidates)}: {candidate['file_id']}")
            
            result = await self.improve_translation(candidate['file_id'], api_key)
            
            if result:
                if result.get('improved'):
                    results['improved'] += 1
                    results['improvements'].append(result)
                elif result.get('reason') == 'no_improvement':
                    results['no_improvement'].append(result)
                else:
                    results['failed'].append(result)
            else:
                results['failed'].append({'file_id': candidate['file_id'], 'error': 'processing_failed'})
            
            # Rate limiting and progress
            if i < len(candidates):
                await asyncio.sleep(2)
        
        # Generate summary
        if results['improved'] > 0:
            avg_improvement = sum(r['improvement'] for r in results['improvements']) / results['improved']
            logger.info(f"✅ Successfully improved {results['improved']}/{results['total_attempted']} files")
            logger.info(f"Average improvement: +{avg_improvement:.1f} points")
        else:
            logger.info("❌ No files were successfully improved")
        
        return results

async def main():
    """Main function to run German translation improvements."""
    setup_logging()
    
    pipeline = GermanImprovementPipeline()
    
    print("🇩🇪 German Translation Improvement System")
    print("=" * 40)
    
    # Get user preferences
    max_files = input("Maximum files to improve (default: 50): ").strip()
    max_files = int(max_files) if max_files.isdigit() else 50
    
    min_score = input("Minimum acceptable score (default: 7.0): ").strip()
    min_score = float(min_score) if min_score else 7.0
    
    print(f"\nImproving up to {max_files} files with scores below {min_score}")
    print("This may take 30-60 minutes depending on the number of files...")
    
    # Run improvements
    results = await pipeline.batch_improve(max_files=max_files, min_score=min_score)
    
    # Save results
    timestamp = int(time.time())
    results_file = f"german_improvement_results_{timestamp}.json"
    
    with open(results_file, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    
    print(f"\n📊 FINAL RESULTS:")
    print(f"Files improved: {results['improved']}/{results['total_attempted']}")
    if results['improved'] > 0:
        avg_improvement = sum(r['improvement'] for r in results['improvements']) / results['improved']
        print(f"Average improvement: +{avg_improvement:.1f} points")
    print(f"Results saved to: {results_file}")

if __name__ == "__main__":
    asyncio.run(main()) 