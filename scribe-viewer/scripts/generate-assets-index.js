#!/usr/bin/env node

const fs = require('fs').promises;
const path = require('path');

async function generateAssetsIndex() {
  console.log('📋 Generating assets index...');
  
  const manifestPath = path.join(__dirname, '../public/manifest.json');
  const assetsIndexPath = path.join(__dirname, '../public/assets-index.json');
  
  try {
    // Load the full manifest
    const manifestContent = await fs.readFile(manifestPath, 'utf-8');
    const manifest = JSON.parse(manifestContent);
    
    // Extract just the id and assets mapping
    const assetsIndex = {};
    manifest.forEach(interview => {
      if (interview.assets) {
        assetsIndex[interview.id] = interview.assets;
      }
    });
    
    // Write the assets index
    await fs.writeFile(assetsIndexPath, JSON.stringify(assetsIndex));
    
    // Get file sizes for comparison
    const manifestStats = await fs.stat(manifestPath);
    const indexStats = await fs.stat(assetsIndexPath);
    
    console.log(`✅ Assets index generated!`);
    console.log(`📊 Original manifest: ${(manifestStats.size / 1024 / 1024).toFixed(2)} MB`);
    console.log(`📊 Assets index: ${(indexStats.size / 1024).toFixed(2)} KB`);
    console.log(`📊 Size reduction: ${((1 - indexStats.size / manifestStats.size) * 100).toFixed(1)}%`);
    
  } catch (error) {
    console.error('❌ Error generating assets index:', error);
    process.exit(1);
  }
}

generateAssetsIndex();