(() => {
  try {
    Object.defineProperty(navigator, 'languages', {
      get: () => ['en-US', 'en'],
      configurable: true,
    });

    const makePlugins = () => {
      const plugins = [
        { name: 'Chrome PDF Plugin' },
        { name: 'Chrome PDF Viewer' },
        { name: 'Native Client' },
      ];
      const pluginArray = {
        length: plugins.length,
        item: (index) => plugins[index] || null,
        namedItem: (name) => plugins.find((p) => p.name === name) || null,
      };
      plugins.forEach((p, i) => {
        Object.defineProperty(pluginArray, i, {
          value: p,
          enumerable: true,
        });
      });
      return pluginArray;
    };

    Object.defineProperty(navigator, 'plugins', {
      get: () => makePlugins(),
      configurable: true,
    });

    if (!('hardwareConcurrency' in navigator)) {
      Object.defineProperty(navigator, 'hardwareConcurrency', {
        get: () => 8,
        configurable: true,
      });
    }
    if (!('deviceMemory' in navigator)) {
      Object.defineProperty(navigator, 'deviceMemory', {
        get: () => 8,
        configurable: true,
      });
    }
  } catch (e) {
    // Ignore if environment is non-standard.
  }
})();
