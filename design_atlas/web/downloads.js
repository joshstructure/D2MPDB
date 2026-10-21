/* Join bounded hosted parts into the exact original document. No calculation. */
(function(root) {
  'use strict';
  async function fetchDocument(document, options={}) {
    const request=options.fetch||root.fetch.bind(root),crypto=options.crypto||root.crypto;
    const hash=async bytes=>Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',bytes)),b=>b.toString(16).padStart(2,'0')).join('');
    const chunks=[];let received=0;
    for(const part of document.parts) {
      if(options.signal?.aborted)throw new DOMException('Download cancelled','AbortError');
      const response=await request(part.href,{signal:options.signal});
      if(!response.ok)throw new Error('The document could not be retrieved. Please retry.');
      const bytes=await response.arrayBuffer();
      if(bytes.byteLength!==part.bytes||await hash(bytes)!==part.sha256)throw new Error('The document failed its integrity check. Refresh the atlas and retry.');
      chunks.push(bytes);received+=bytes.byteLength;options.onProgress?.(received,document.bytes);
    }
    const blob=new Blob(chunks,{type:'application/octet-stream'});
    if(blob.size!==document.bytes||await hash(await blob.arrayBuffer())!==document.sha256)throw new Error('The document failed its integrity check. Refresh the atlas and retry.');
    if(options.signal?.aborted)throw new DOMException('Download cancelled','AbortError');
    return blob;
  }
  root.AtlasDownloads={fetchDocument};
  if(typeof module==='object')module.exports=root.AtlasDownloads;
})(typeof globalThis!=='undefined'?globalThis:this);
