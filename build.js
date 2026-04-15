// Cross-platform build script for Netlify
// Replaces %%RAILWAY_URL%% in frontend/index.html with RAILWAY_BACKEND_URL env var
const fs = require('fs');

const url = process.env.RAILWAY_BACKEND_URL || 'http://localhost:8000';
if (!process.env.RAILWAY_BACKEND_URL) {
  console.warn('RAILWAY_BACKEND_URL not set — using http://localhost:8000 for local dev');
}

const src = fs.readFileSync('frontend/index.html', 'utf8');
const out = src.replace(/%%RAILWAY_URL%%/g, url);
fs.mkdirSync('dist', { recursive: true });
fs.writeFileSync('dist/index.html', out);
console.log('Built dist/index.html — API:', url);
