(() => {
  try {
    if (HTMLCanvasElement.prototype.__tavily_canvas_patched__) {
      return;
    }
    HTMLCanvasElement.prototype.__tavily_canvas_patched__ = true;

    const originalGetImageData =
      CanvasRenderingContext2D.prototype.getImageData;

    CanvasRenderingContext2D.prototype.getImageData = function (x, y, w, h) {
      const imageData = originalGetImageData.call(this, x, y, w, h);
      try {
        const { data } = imageData;
        for (let i = 0; i < data.length; i += 40) {
          data[i] = data[i] ^ 0x01;
          data[i + 1] = data[i + 1] ^ 0x01;
          data[i + 2] = data[i + 2] ^ 0x01;
        }
      } catch (e) {
        // If anything fails, return unmodified data.
      }
      return imageData;
    };
  } catch (e) {
    // Leave canvas untouched if environment differs.
  }
})();
