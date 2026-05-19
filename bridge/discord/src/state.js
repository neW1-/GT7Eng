export class BridgeState {
  constructor({ mode = "quiet_driver", engineerMuted = false } = {}) {
    this.mode = mode;
    this.engineerMuted = engineerMuted;
    this.voiceChannelId = null;
    this.driverUserId = null;
    this.lastDriverAudioAt = null;
    this.driverAudioPackets = 0;
    this.lastJobId = null;
    this.lastError = null;
    this.startedAt = new Date();
  }

  snapshot() {
    return {
      mode: this.mode,
      engineerMuted: this.engineerMuted,
      voiceChannelId: this.voiceChannelId,
      driverUserId: this.driverUserId,
      lastDriverAudioAt: this.lastDriverAudioAt,
      driverAudioPackets: this.driverAudioPackets,
      lastJobId: this.lastJobId,
      lastError: this.lastError,
      uptimeSeconds: Math.floor((Date.now() - this.startedAt.getTime()) / 1000)
    };
  }
}
