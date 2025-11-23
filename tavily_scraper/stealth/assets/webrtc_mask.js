(() => {
  try {
    const RTC = window.RTCPeerConnection || window.webkitRTCPeerConnection;
    if (RTC && !RTC.prototype.__tavily_webrtc_patched__) {
      RTC.prototype.__tavily_webrtc_patched__ = true;

      const origCreateDataChannel = RTC.prototype.createDataChannel;
      RTC.prototype.createDataChannel = function () {
        try {
          this.__tavily_webrtc_dc__ = true;
        } catch (e) {}
        return origCreateDataChannel.apply(this, arguments);
      };

      const origOnIceCandidateDesc = Object.getOwnPropertyDescriptor(
        RTC.prototype,
        'onicecandidate',
      );
      Object.defineProperty(RTC.prototype, 'onicecandidate', {
        set: function (handler) {
          const wrapped = (event) => {
            try {
              if (event && event.candidate && event.candidate.candidate) {
                const c = event.candidate.candidate;
                const sanitized = c.replace(
                  /(candidate:\\d+ \\d+ udp \\d+ )([0-9.]+)( .*)/,
                  '$10.0.0.0$3',
                );
                event = new RTCIceCandidate({
                  sdpMid: event.candidate.sdpMid,
                  sdpMLineIndex: event.candidate.sdpMLineIndex,
                  candidate: sanitized,
                });
              }
            } catch (e) {}
            return handler ? handler(event) : undefined;
          };
          if (origOnIceCandidateDesc && origOnIceCandidateDesc.set) {
            return origOnIceCandidateDesc.set.call(this, wrapped);
          }
          this._onicecandidate = wrapped;
        },
        get: function () {
          return this._onicecandidate;
        },
        configurable: true,
      });
    }

    if (navigator.mediaDevices && navigator.mediaDevices.enumerateDevices) {
      const origEnum = navigator.mediaDevices.enumerateDevices.bind(
        navigator.mediaDevices,
      );
      navigator.mediaDevices.enumerateDevices = () =>
        origEnum()
          .then((list) => {
            if (list && list.length > 0) return list;
            return [
              {
                kind: 'audioinput',
                label: 'Default - Microphone',
                deviceId: 'default',
                groupId: 'default',
              },
              {
                kind: 'audiooutput',
                label: 'Default - Speakers',
                deviceId: 'default',
                groupId: 'default',
              },
            ];
          })
          .catch(() => [
            {
              kind: 'audioinput',
              label: 'Default - Microphone',
              deviceId: 'default',
              groupId: 'default',
            },
            {
              kind: 'audiooutput',
              label: 'Default - Speakers',
              deviceId: 'default',
              groupId: 'default',
            },
          ]);
    }
  } catch (e) {
    // Ignore if WebRTC is unavailable
  }
})();
