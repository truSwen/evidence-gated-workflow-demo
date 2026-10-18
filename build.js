// One shared HTML + UI module, two explicit adapters. No UI code generation or
// string replacement of backend calls. The server and build use /entry.js.
import {mkdir,readFile,writeFile,rm} from 'node:fs/promises';
import {build} from 'esbuild';
await rm('dist',{recursive:true,force:true});
await mkdir('dist',{recursive:true});
for(const name of ['index.html','style.css'])await writeFile(`dist/${name}`,await readFile(name));
await build({entryPoints:['browser-entry.js'],bundle:true,format:'esm',platform:'browser',outfile:'dist/entry.js',minify:true});
await writeFile('dist/_headers',`/*
  X-Content-Type-Options: nosniff
  Referrer-Policy: no-referrer
  Content-Security-Policy: default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'
`);
await writeFile('dist/404.html','<!doctype html><html lang="en"><title>Not found</title><a href="/">Open the synthetic workflow</a></html>');
