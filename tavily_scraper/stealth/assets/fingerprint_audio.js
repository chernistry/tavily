(() => {
  try {
    const AudioCtx = window.AudioContext || window.webkitAudioContext;
    if (!AudioCtx || AudioCtx.prototype.__tavily_audio_patched__) {
      return;
    }
    AudioCtx.prototype.__tavily_audio_patched__ = true;

    const originalGetChannelData = AudioCtx.prototype.getChannelData;

    AudioCtx.prototype.getChannelData = function () {
      const results = originalGetChannelData.apply(this, arguments);
      try {
        const len = results.length;
        const stride = Math.max(1, Math.floor(len / 500));
        for (let i = 0; i < len; i += stride) {
          results[i] = results[i] + (Math.random() - 0.5) * 1e-7;
        }
      } catch (e) {
        // Ignore if typed arrays behave unexpectedly
      }
      return results;
    };
  } catch (e) {
    // No-op if AudioContext is unavailable
  }
})();
