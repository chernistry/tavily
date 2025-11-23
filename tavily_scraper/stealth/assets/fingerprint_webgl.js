(() => {
  try {
    const patchContext = (WebGLClass) => {
      if (!WebGLClass || WebGLClass.prototype.__tavily_webgl_patched__) {
        return;
      }
      WebGLClass.prototype.__tavily_webgl_patched__ = true;

      const getParameter = WebGLClass.prototype.getParameter;
      WebGLClass.prototype.getParameter = function (parameter) {
        try {
          const debugInfo =
            this.getExtension && this.getExtension('WEBGL_debug_renderer_info');
          if (debugInfo) {
            if (parameter === debugInfo.UNMASKED_VENDOR_WEBGL) {
              return "__WEBGL_VENDOR__";
            }
            if (parameter === debugInfo.UNMASKED_RENDERER_WEBGL) {
              return "__WEBGL_RENDERER__";
            }
          }
          // Standard constants often probed
          if (parameter === 37445) return "__WEBGL_VENDOR__";
          if (parameter === 37446) return "__WEBGL_RENDERER__";

          // Spoof other common fingerprinting parameters if needed
          // For now, we focus on vendor/renderer as they are the high-entropy bits

        } catch (e) {
          // fall through
        }
        return getParameter.call(this, parameter);
      };

      // Hook getSupportedExtensions to potentially mask some extensions if we wanted to be very stealthy
      // For now, we just ensure it doesn't leak that we are headless if there are specific headless-only extensions
      // (Chromium headless usually looks fine, but we can shuffle the order to be safe/unique)
      const getSupportedExtensions = WebGLClass.prototype.getSupportedExtensions;
      WebGLClass.prototype.getSupportedExtensions = function () {
        const extensions = getSupportedExtensions.call(this);
        if (extensions && extensions.length > 0) {
          // Simple shuffle based on a seed would be better, but random is okay for "noise"
          // However, we want stability within session. 
          // Let's just leave it as is for now unless we have a specific list to hide.
          return extensions;
        }
        return extensions;
      };

      // Hook getShaderPrecisionFormat to return consistent values
      // (Headless sometimes differs from headful, but usually it's GPU dependent)
      // We'll leave this for now as it requires complex mocking of all precision types.

    };

    if (typeof WebGLRenderingContext !== 'undefined') {
      patchContext(WebGLRenderingContext);
    }
    if (typeof WebGL2RenderingContext !== 'undefined') {
      patchContext(WebGL2RenderingContext);
    }
  } catch (e) {
    // Leave WebGL untouched if environment differs.
  }
})();
