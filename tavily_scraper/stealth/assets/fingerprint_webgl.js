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
          if (parameter === 37445) {
            return "__WEBGL_VENDOR__";
          }
          if (parameter === 37446) {
            return "__WEBGL_RENDERER__";
          }
        } catch (e) {
          // fall through
        }
        return getParameter.call(this, parameter);
      };
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
