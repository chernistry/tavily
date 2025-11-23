(() => {
  try {
    if (HTMLCanvasElement.prototype.__tavily_canvas_patched__) {
      return;
    }
    HTMLCanvasElement.prototype.__tavily_canvas_patched__ = true;

    // --- Helper: Stable Noise Generator ---
    const getNoise = (val, idx) => {
      // Simple hash-based noise
      const seed = (val * idx) + (window.__TAVILY_SEED__ || 12345);
      const x = Math.sin(seed) * 10000;
      return (x - Math.floor(x)); // 0..1
    };

    // --- 1. Patch getImageData ---
    const originalGetImageData = CanvasRenderingContext2D.prototype.getImageData;
    CanvasRenderingContext2D.prototype.getImageData = function (x, y, w, h) {
      const imageData = originalGetImageData.call(this, x, y, w, h);
      try {
        const { data } = imageData;
        // Apply noise to a subset of pixels to avoid performance hit
        for (let i = 0; i < data.length; i += 40) {
          // Noise -2 to +2
          const noise = Math.floor(getNoise(i, data[i]) * 5) - 2;
          // Modulate channels slightly
          data[i] = Math.max(0, Math.min(255, data[i] + noise));
          data[i + 1] = Math.max(0, Math.min(255, data[i + 1] + noise));
          data[i + 2] = Math.max(0, Math.min(255, data[i + 2] + noise));
        }
      } catch (e) {
        // If anything fails, return unmodified data.
      }
      return imageData;
    };

    // --- 2. Patch toDataURL ---
    const originalToDataURL = HTMLCanvasElement.prototype.toDataURL;
    HTMLCanvasElement.prototype.toDataURL = function (type, encoderOptions) {
      let originalTL = null;
      let originalBR = null;
      let ctx = null;

      try {
        ctx = this.getContext("2d");
        if (ctx) {
          const w = this.width;
          const h = this.height;
          const seed = (window.__TAVILY_SEED__ || 12345);
          const noiseVal = (seed % 3) + 1;

          // Patch top-left
          const imgDataTL = ctx.getImageData(0, 0, 1, 1);
          originalTL = ctx.getImageData(0, 0, 1, 1); // Save copy

          // Modify Alpha to ensure hash change
          let a = imgDataTL.data[3];
          if (a === 0) a = 1;
          else if (a === 255) a = 254;
          else a = (a + noiseVal) % 256;
          imgDataTL.data[3] = a;
          ctx.putImageData(imgDataTL, 0, 0);

          // Patch bottom-right
          if (w > 1 || h > 1) {
            const imgDataBR = ctx.getImageData(w - 1, h - 1, 1, 1);
            originalBR = ctx.getImageData(w - 1, h - 1, 1, 1); // Save copy

            let a2 = imgDataBR.data[3];
            if (a2 === 0) a2 = 1;
            else if (a2 === 255) a2 = 254;
            else a2 = (a2 + noiseVal) % 256;
            imgDataBR.data[3] = a2;
            ctx.putImageData(imgDataBR, w - 1, h - 1);
          }
        }
      } catch (e) {
        // Ignore errors
      }

      const result = originalToDataURL.call(this, type, encoderOptions);

      // Restore
      if (ctx) {
        try {
          if (originalTL) ctx.putImageData(originalTL, 0, 0);
          if (originalBR) ctx.putImageData(originalBR, this.width - 1, this.height - 1);
        } catch (e) { }
      }

      return result;
    };

    // --- 3. Patch toBlob ---
    const originalToBlob = HTMLCanvasElement.prototype.toBlob;
    HTMLCanvasElement.prototype.toBlob = function (callback, type, quality) {
      try {
        const ctx = this.getContext("2d");
        if (ctx) {
          const w = this.width;
          const h = this.height;
          const tempCanvas = document.createElement('canvas');
          tempCanvas.width = w;
          tempCanvas.height = h;
          const tempCtx = tempCanvas.getContext('2d');
          tempCtx.drawImage(this, 0, 0);

          const seed = (window.__TAVILY_SEED__ || 12345);
          const noiseVal = (seed % 3) + 1;

          const imgDataTL = tempCtx.getImageData(0, 0, 1, 1);
          let a = imgDataTL.data[3];
          if (a === 0) a = 1;
          else if (a === 255) a = 254;
          else a = (a + noiseVal) % 256;
          imgDataTL.data[3] = a;
          tempCtx.putImageData(imgDataTL, 0, 0);

          return originalToBlob.call(tempCanvas, callback, type, quality);
        }
      } catch (e) {
        // Fallback
      }
      return originalToBlob.call(this, callback, type, quality);
    };

  } catch (e) {
    console.error("Tavily Canvas Patch Error:", e);
  }
})();
