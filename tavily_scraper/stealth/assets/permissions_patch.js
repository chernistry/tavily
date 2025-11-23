(() => {
  try {
    const permissions = window.navigator.permissions;
    if (!permissions || !permissions.query) {
      return;
    }

    const originalQuery = permissions.query.bind(permissions);

    permissions.query = (parameters) => {
      try {
        if (parameters && parameters.name === 'notifications') {
          const defaultState =
            (typeof Notification !== 'undefined' && Notification.permission) ||
            'default';
          return Promise.resolve({ state: defaultState });
        }
        return originalQuery(parameters);
      } catch (e) {
        const fallbackState =
          (typeof Notification !== 'undefined' && Notification.permission) ||
          'default';
        return Promise.resolve({ state: fallbackState });
      }
    };
  } catch (e) {
    // Do nothing if permissions API behaves differently.
  }
})();
