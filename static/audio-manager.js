class AudioManager {
  constructor() {
    this.clickBuffer = null;
    this.lastClickTime = 0;
    this.clickCooldown = 200;
    this.audioContext = null;
    this.currentSource = null;
    this.currentKicksSource = null;
    this.currentBuffer = null;
    this.currentAnalyser = null;
    this.currentGainNode = null;
    this.currentPage = this.detectCurrentPage();
    this.fadeSpeed = 0.15;
    this.fadeTimer = null;
    this.isPlaying = false;
    this.visualizerActive = false;
    this.isMuted = false;
    this.isAhh = false;
    this.maxAhh = 0;
  }

  playClick(volume = 0.7) {
    if (!this.clickBuffer || this.isMuted || this.isAhh) return;

    const now = performance.now();
    if (now - this.lastClickTime < this.clickCooldown) return;
    this.lastClickTime = now;

    const source = this.audioContext.createBufferSource();
    source.buffer = this.clickBuffer;

    const gain = this.audioContext.createGain();
    gain.gain.value = volume;

    source.connect(gain);
    gain.connect(this.audioContext.destination);

    source.start();
  }


  async initAudioContext() {
    if (!this.audioContext) {
      this.audioContext = new (window.AudioContext || window.webkitAudioContext)();
    }
    if (this.audioContext.state === 'suspended') {
      await this.audioContext.resume();
    }
    return this.audioContext;
  }
  async loadClickSound() {
    if (this.clickBuffer) return;

    const response = await fetch('/static/sounds/ahh.mp3');
    const arrayBuffer = await response.arrayBuffer();
    this.clickBuffer = await this.audioContext.decodeAudioData(arrayBuffer);
  }


  detectCurrentPage() {
    const path = window.location.pathname;
    if (path === '/login') return 'login';
    if (path === '/register') return 'login';
    if (path === '/create') return 'create';
    return 'main';
  }

  fadeOut(gainNode, callback) {
    if (this.fadeTimer) clearInterval(this.fadeTimer);
    const startVolume = gainNode.gain.value;
    const steps = 10;
    let currentStep = 0;

    this.fadeTimer = setInterval(() => {
      currentStep++;
      const progress = currentStep / steps;
      gainNode.gain.value = startVolume * (1 - progress);

      if (currentStep >= steps) {
        clearInterval(this.fadeTimer);
        gainNode.gain.value = 0;
        if (callback) callback();
      }
    }, 50);
  }

  fadeIn(gainNode) {
    if (this.fadeTimer) clearInterval(this.fadeTimer);
    if (this.isMuted) {
      gainNode.gain.value = 0;
      return;
    }
    gainNode.gain.value = 0;
    const steps = 10;
    let currentStep = 0;

    this.fadeTimer = setInterval(() => {
      currentStep++;
      const progress = currentStep / steps;
      gainNode.gain.value = 0.5 * progress;

      if (currentStep >= steps) {
        clearInterval(this.fadeTimer);
        gainNode.gain.value = 0.5;
      }
    }, 50);
  }

  async loadAudioBuffers(loopName) {
    const audioPath = `/static/sounds/music/${loopName}.wav`;
    const kicksPath = `/static/sounds/music/${loopName}-kicks.wav`;
    const ctx = this.audioContext;

    const response = await fetch(audioPath);
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}: ${response.statusText}`);
    }
    const arrayBuffer = await response.arrayBuffer();
    const audioBuffer = await ctx.decodeAudioData(arrayBuffer);

    let kicksBuffer = null;
    try {
      const kicksResponse = await fetch(kicksPath);
      if (kicksResponse.ok) {
        const kicksArrayBuffer = await kicksResponse.arrayBuffer();
        kicksBuffer = await ctx.decodeAudioData(kicksArrayBuffer);
      }
    } catch (e) {
      kicksBuffer = audioBuffer;
    }

    return { audioBuffer, kicksBuffer };
  }

  async playLoop(loopName, skipFadeIn = false, preloadedBuffers = null) {
    const ctx = this.audioContext;

    try {
      let audioBuffer, kicksBuffer;
      if (preloadedBuffers) {
        audioBuffer = preloadedBuffers.audioBuffer;
        kicksBuffer = preloadedBuffers.kicksBuffer;
      } else {
        const buffers = await this.loadAudioBuffers(loopName);
        audioBuffer = buffers.audioBuffer;
        kicksBuffer = buffers.kicksBuffer;
      }

      const gainNode = ctx.createGain();
      gainNode.gain.value = this.isMuted ? 0 : 0.5;
      
      const analyser = ctx.createAnalyser();
      analyser.fftSize = 512;
      analyser.smoothingTimeConstant = 0.8;

      gainNode.connect(ctx.destination);
      gainNode.connect(analyser);

      const playAudio = () => {
        const source = ctx.createBufferSource();
        source.buffer = audioBuffer;
        source.loop = true;
        source.connect(gainNode);

        const kicksSource = ctx.createBufferSource();
        kicksSource.buffer = kicksBuffer;
        kicksSource.loop = true;
        const kicksGain = ctx.createGain();
        kicksGain.gain.value = 0;
        kicksSource.connect(kicksGain);
        kicksGain.connect(analyser);

        if (this.currentSource) {
          this.visualizerActive = false;
          this.fadeOut(gainNode, () => {
            try {
              this.currentSource.stop();
              this.currentSource.disconnect();
            } catch (e) {}
            if (this.currentKicksSource) {
              try {
                this.currentKicksSource.stop();
                this.currentKicksSource.disconnect();
              } catch (e) {}
            }
            source.start(0);
            kicksSource.start(0);
            this.fadeIn(gainNode);
            this.startVisualization(analyser);
          });
        } else {
          source.start(0);
          kicksSource.start(0);
          if (!skipFadeIn) {
            this.fadeIn(gainNode);
          }
          this.startVisualization(analyser);
        }

        this.currentSource = source;
        this.currentKicksSource = kicksSource;
        this.currentBuffer = audioBuffer;
        this.currentGainNode = gainNode;
        this.isPlaying = true;
      };

      playAudio();
    } catch (err) {
      console.error('Audio playback failed:', err);
    }
  }

  startVisualization(analyser) {
    if (this.visualizerActive) return;
    this.visualizerActive = true;
    this.currentAnalyser = analyser;

    const dataArray = new Uint8Array(analyser.frequencyBinCount);
    let frameCount = 0;

    const visualize = () => {
      if (!this.visualizerActive) return;

      analyser.getByteFrequencyData(dataArray);

      const lowFreqBins = dataArray.slice(0, 40);
      const maxFreq = Math.max(...lowFreqBins);
      const avgFreq = lowFreqBins.reduce((a, b) => a + b) / lowFreqBins.length;
      
      let kickIntensity = Math.max(0, (maxFreq - 40) / 150);
      let ahhIntensity = kickIntensity * 100;
      
      const currentPage = this.detectCurrentPage();
      if (currentPage === 'create') {
        kickIntensity = 1.5 - kickIntensity;
        kickIntensity *= 9;
        ahhIntensity = kickIntensity * 100;
        ahhIntensity -= 30;
        /*console.log("Kick intensity:", kickIntensity);*/
      }

      const contentDiv = document.querySelector('.content');
      if(ahhIntensity > this.maxAhh) {
        this.maxAhh = ahhIntensity;
      } else if(this.maxAhh > 160){
        this.maxAhh = 0;
      }
      if (contentDiv) {
        if (kickIntensity > 1.365) {
          contentDiv.style.backgroundColor = `hsl(180deg, 50%, 70%)`;
        } else if (kickIntensity <= 1) {
          contentDiv.style.backgroundColor = `hsl(180deg, 100%, 9.41%)`;
        } else if (this.isMuted) {
          contentDiv.style.backgroundColor = `hsl(180deg, 100%, 9.41%)`;
        } else {
          const baseSaturation = 100;
          const baseLightness = 9.41;

          const saturation = Math.max(0, baseSaturation - kickIntensity * 10) + 13;
          const lightness = Math.min(90, Math.max(baseLightness, baseLightness + kickIntensity * 8)) - (19-baseLightness);

          contentDiv.style.backgroundColor = `hsl(180deg, ${saturation}%, ${lightness}%)`;
        }
        contentDiv.style.transition = 'background-color 0.5s ease-out';
        /*console.log("kickIntensity: ", kickIntensity)*/
        console.log("ahhIntensity", this.maxAhh)
        /*console.log("current frame", frameCount)*/
      }

      requestAnimationFrame(visualize);
    };

    visualize();
  }

  toggleMute() {
    if (!this.currentGainNode) return;
    
    this.isMuted = !this.isMuted;
    
    if (this.isMuted) {
      this.currentGainNode.gain.value = 0;
      this.visualizerActive = false;
      const contentDiv = document.querySelector('.content');
      if(contentDiv){contentDiv.style.backgroundColor = "hsl(180deg, 100%, 9.41%)"}
    } else {
      this.currentGainNode.gain.value = 0.5;
      if (this.isPlaying) {
        this.startVisualization(this.currentAnalyser);
      }
    }
    
    const muteBtn = document.getElementById('mute-btn');
    if (muteBtn) {
      muteBtn.classList.toggle('muted', this.isMuted);
    }
  }

  toggleAhh() {
    if (!this.currentGainNode) return;
    
    this.isAhh = !this.isAhh;
    
    const ahhBtn = document.getElementById('ahh-btn');
    if (muteBtn) {
      ahhBtn.classList.toggle('muted', this.isAhh);
    }
  }

  scheduleTransition(loopName) {
    this.currentPage = loopName === 'login' ? 'login' : loopName === 'create' ? 'create' : 'main';
    this.playLoop(loopName);
  }

  async playIntro() {
    const introPath = `/static/sounds/music/intro.wav`;
    const introKicksPath = `/static/sounds/music/intro-kicks.wav`;
    const ctx = this.audioContext;

    try {
      const response = await fetch(introPath);
      const arrayBuffer = await response.arrayBuffer();
      const introBuffer = await ctx.decodeAudioData(arrayBuffer);

      let introKicksBuffer = null;
      try {
        const kicksResponse = await fetch(introKicksPath);
        if (kicksResponse.ok) {
          const kicksArrayBuffer = await kicksResponse.arrayBuffer();
          introKicksBuffer = await ctx.decodeAudioData(kicksArrayBuffer);
        }
      } catch (e) {
        introKicksBuffer = introBuffer;
      }

      const gainNode = ctx.createGain();
      gainNode.gain.value = 0;
      
      const analyser = ctx.createAnalyser();
      analyser.fftSize = 512;
      analyser.smoothingTimeConstant = 0.8;

      gainNode.connect(ctx.destination);
      gainNode.connect(analyser);

      const source = ctx.createBufferSource();
      source.buffer = introBuffer;
      source.connect(gainNode);

      const kicksSource = ctx.createBufferSource();
      kicksSource.buffer = introKicksBuffer;
      const kicksGain = ctx.createGain();
      kicksGain.gain.value = 0;
      kicksSource.connect(kicksGain);
      kicksGain.connect(analyser);

      this.currentGainNode = gainNode;
      this.currentSource = source;
      this.currentKicksSource = kicksSource;
      this.currentAnalyser = analyser;
      this.isPlaying = true;
      
      this.fadeIn(gainNode);
      this.startVisualization(analyser);
      
      return new Promise((resolve) => {
        source.onended = () => {
          this.visualizerActive = false;
          this.currentSource = null;
          this.currentKicksSource = null;
          resolve(true);
        };
        source.start(0);
        kicksSource.start(0);
      });
    } catch (err) {
      console.error('Intro playback failed:', err);
      return false;
    }
  }

  async init() {
    const newPage = this.detectCurrentPage();
    this.currentPage = newPage;
    this.setupNavigationListeners();
    this.setupHistoryListener();
    this.loadClickSound();
    
    await this.initAudioContext();
    
    let playedIntro = false;
    let preloadedBuffers = null;
    
    if (newPage === 'main') {
      const [intro, buffers] = await Promise.all([
        this.playIntro(),
        this.loadAudioBuffers(this.currentPage)
      ]);
      playedIntro = intro;
      preloadedBuffers = buffers;
    }
    
    await this.playLoop(this.currentPage, playedIntro, preloadedBuffers);
  }

  setupHistoryListener() {
    window.addEventListener('popstate', () => {
      const newPage = this.detectCurrentPage();
      if (newPage !== this.currentPage) {
        this.scheduleTransition(newPage);
      }
    });
  }

  setupNavigationListeners() {
    document.addEventListener('click', (e) => {
      const link = e.target.closest('a');
      if (link && link.href && !link.target) {
        const href = new URL(link.href, window.location.origin).pathname;
        
        let loopName = null;
        if (href === '/login' || href === '/register') {
          loopName = 'login';
        } else if (href === '/create') {
          loopName = 'create';
        } else if (href === '/') {
          loopName = 'main';
        }

        if (loopName) {
          e.preventDefault();
          window.location.href = href;
        }
      }
    });
  }

}

const audioManager = new AudioManager();
window.audioManager = audioManager;
document.addEventListener('DOMContentLoaded', () => {
  audioManager.init();
});
