/**
 * Polyfills for browser APIs needed by Three.js GLTFExporter in Node.js.
 * Must be imported before GLTFExporter.
 */

// FileReader polyfill — used by GLTFExporter to read Blob data
if (typeof globalThis.FileReader === 'undefined') {
  globalThis.FileReader = class FileReader {
    _fire(result) {
      this.result = result;
      if (typeof this.onload === 'function') this.onload({ target: this });
      if (typeof this.onloadend === 'function') this.onloadend({ target: this });
    }
    _fireError(err) {
      if (typeof this.onerror === 'function') this.onerror(err);
      if (typeof this.onloadend === 'function') this.onloadend({ target: this });
    }
    readAsArrayBuffer(blob) {
      Promise.resolve(blob.arrayBuffer())
        .then(buf => this._fire(buf))
        .catch(err => this._fireError(err));
    }
    readAsDataURL(blob) {
      Promise.resolve(blob.arrayBuffer()).then(buf => {
        const b64 = Buffer.from(buf).toString('base64');
        const mime = blob.type || 'application/octet-stream';
        this._fire(`data:${mime};base64,${b64}`);
      }).catch(err => this._fireError(err));
    }
  };
}

// URL polyfill helpers for GLTFExporter (createObjectURL not needed for binary export)
if (typeof globalThis.URL !== 'undefined') {
  if (typeof globalThis.URL.createObjectURL === 'undefined') {
    globalThis.URL.createObjectURL = () => '';
    globalThis.URL.revokeObjectURL = () => {};
  }
}
