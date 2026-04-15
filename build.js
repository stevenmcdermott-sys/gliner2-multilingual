// Cross-platform build script for Netlify
// Replaces %%RAILWAY_URL%% in frontend/index.html with RAILWAY_BACKEND_URL env var
const fs = require('fs');

const url = process.env.RAILWAY_BACKEND_URL || '';
if (!url) {
  console.error('ERROR: RAILWAY_BACKEND_URL environment variable is not set.');
  process.exit(1);
}

const src = fs.readFileSync('frontend/index.html', 'utf8');
const out = src.replace(/%%RAILWAY_URL%%/g, url);
fs.mkdirSync('dist', { recursive: true });
fs.writeFileSync('dist/index.html', out);
console.log('Built dist/index.html — API:', url);
