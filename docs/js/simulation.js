/**
 * Game simulation engine.
 * Handles typewriter effects, turn sequencing, score animation, and phase transitions.
 */

class GameSimulation {
  constructor() {
    this.currentTurn = 0;
    this.redScore = 0;
    this.blueScore = 0;
    this.isPlaying = false;
    this.isPaused = false;
    this.speed = 1;
    this.killChainReached = new Set();
    this.typewriterTimeout = null;
    this.turnTimeout = null;
    this.hasStarted = false;
    this.isComplete = false;
    this.turnInProgress = false;

    this.redTerminal = document.getElementById('red-terminal-body');
    this.blueTerminal = document.getElementById('blue-terminal-body');
    this.redScoreEl = document.getElementById('red-score');
    this.blueScoreEl = document.getElementById('blue-score');
    this.phaseEl = document.getElementById('phase-indicator');
    this.turnEl = document.getElementById('turn-counter');
    this.playBtn = document.getElementById('play-btn');
    this.speedBtns = document.querySelectorAll('.speed-btn');

    this._bindControls();
  }

  _bindControls() {
    this.playBtn.addEventListener('click', () => this._togglePlay());

    this.speedBtns.forEach(btn => {
      btn.addEventListener('click', () => {
        this.speedBtns.forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        this.speed = parseFloat(btn.dataset.speed);
      });
    });
  }

  _togglePlay() {
    if (this.isComplete) {
      this._reset();
      this._play();
      return;
    }
    if (this.isPlaying && !this.isPaused) {
      this._pause();
    } else {
      this._play();
    }
  }

  _play() {
    this.isPlaying = true;
    this.isPaused = false;
    this.playBtn.innerHTML = '<span class="btn-icon">&#9646;&#9646;</span> Pause';
    this.playBtn.classList.add('playing');
    if (!this.hasStarted) {
      this.hasStarted = true;
    }
    // Small delay so DOM can settle after unpause
    setTimeout(() => this._runNextTurn(), 100);
  }

  _pause() {
    this.isPaused = true;
    this.playBtn.innerHTML = '<span class="btn-icon">&#9654;</span> Play';
    this.playBtn.classList.remove('playing');
    clearTimeout(this.turnTimeout);
    clearTimeout(this.typewriterTimeout);
  }

  _reset() {
    this.currentTurn = 0;
    this.redScore = 0;
    this.blueScore = 0;
    this.isPlaying = false;
    this.isPaused = false;
    this.hasStarted = false;
    this.isComplete = false;
    this.killChainReached = new Set();
    this.turnInProgress = false;
    clearTimeout(this.turnTimeout);
    clearTimeout(this.typewriterTimeout);

    this.redTerminal.innerHTML = '';
    this.blueTerminal.innerHTML = '';
    this._updateScores(false);
    this._updatePhase(GAME_PHASES.SETUP);
    this.turnEl.textContent = 'Turn 0 / 16';
    this._resetKillChain();
    this.playBtn.innerHTML = '<span class="btn-icon">&#9654;</span> Play';
    this.playBtn.classList.remove('playing');
  }

  startIfVisible() {
    if (this.hasStarted) return;
    this._play();
  }

  _runNextTurn() {
    if (this.isPaused || this.currentTurn >= GAME_TURNS.length) {
      if (this.currentTurn >= GAME_TURNS.length && !this.isComplete) {
        this._showConclusion();
      }
      return;
    }

    // If resuming from pause mid-turn, skip the interrupted turn
    // (its partial DOM is already visible, advance to avoid duplicates)
    if (this.turnInProgress) {
      this.currentTurn++;
      this.turnInProgress = false;
      if (this.currentTurn >= GAME_TURNS.length) {
        this._showConclusion();
        return;
      }
    }

    this.turnInProgress = true;
    const turn = GAME_TURNS[this.currentTurn];
    this._updatePhase(turn.phase);
    this.turnEl.textContent = `Turn ${turn.turn} / 16`;

    const terminal = turn.team === TEAMS.RED ? this.redTerminal : this.blueTerminal;
    const prompt = turn.team === TEAMS.RED ? 'red-agent$' : 'blue-agent$';
    const teamClass = turn.team === TEAMS.RED ? 'red' : 'blue';

    // Create turn block
    const turnBlock = document.createElement('div');
    turnBlock.className = `turn-block ${teamClass}`;

    const labelEl = document.createElement('div');
    labelEl.className = 'turn-label';
    labelEl.textContent = `[Turn ${turn.turn}] ${turn.label}`;
    if (turn.stealth) {
      labelEl.innerHTML += ' <span class="stealth-badge">STEALTH</span>';
    }
    turnBlock.appendChild(labelEl);

    const promptLine = document.createElement('div');
    promptLine.className = 'prompt-line';
    promptLine.innerHTML = `<span class="prompt ${teamClass}">${prompt} </span><span class="command-text"></span><span class="cursor blink">_</span>`;
    turnBlock.appendChild(promptLine);

    terminal.appendChild(turnBlock);
    this._scrollTerminal(terminal);

    // Typewriter the command
    const commandEl = promptLine.querySelector('.command-text');
    const cursorEl = promptLine.querySelector('.cursor');

    this._typewrite(commandEl, turn.command, () => {
      if (this.isPaused) return;
      cursorEl.classList.remove('blink');
      cursorEl.style.display = 'none';

      // Show output after a beat
      this.turnTimeout = setTimeout(() => {
        if (this.isPaused) return;

        if (turn.output) {
          const outputEl = document.createElement('div');
          outputEl.className = 'output-text';
          outputEl.textContent = turn.output;
          turnBlock.appendChild(outputEl);
          outputEl.classList.add('fade-in');
        }

        // Update scores
        if (turn.scoreDelta.red) {
          this.redScore += turn.scoreDelta.red;
        }
        if (turn.scoreDelta.blue) {
          this.blueScore += turn.scoreDelta.blue;
        }
        this._updateScores(true);

        // Update kill chain
        if (turn.killChain) {
          this.killChainReached.add(turn.killChain);
          this._updateKillChain();
        }

        // Show event badge
        const eventEl = document.createElement('div');
        eventEl.className = `event-badge ${teamClass}`;
        eventEl.textContent = turn.event.replace(/_/g, ' ');
        if (turn.scoreDelta.red) {
          eventEl.textContent += ` (+${turn.scoreDelta.red})`;
        }
        if (turn.scoreDelta.blue) {
          eventEl.textContent += ` (+${turn.scoreDelta.blue})`;
        }
        turnBlock.appendChild(eventEl);
        eventEl.classList.add('fade-in');

        this._scrollTerminal(terminal);

        this.turnInProgress = false;
        this.currentTurn++;
        const delay = 1800 / this.speed;
        this.turnTimeout = setTimeout(() => this._runNextTurn(), delay);

      }, 400 / this.speed);
    });
  }

  _typewrite(element, text, callback) {
    let i = 0;
    const charsPerTick = Math.max(1, Math.floor(this.speed));
    const interval = 28 / this.speed;

    const type = () => {
      if (this.isPaused) return;
      if (i < text.length) {
        const end = Math.min(i + charsPerTick, text.length);
        element.textContent = text.substring(0, end);
        i = end;
        this._scrollTerminal(element.closest('.terminal-body'));
        this.typewriterTimeout = setTimeout(type, interval);
      } else {
        callback();
      }
    };
    type();
  }

  _scrollTerminal(terminal) {
    terminal.scrollTop = terminal.scrollHeight;
  }

  _updateScores(animate) {
    this._animateScore(this.redScoreEl, this.redScore, animate);
    this._animateScore(this.blueScoreEl, this.blueScore, animate);

    // Update score bar
    const total = Math.max(this.redScore + this.blueScore, 1);
    const redPct = (this.redScore / total) * 100;
    const bluePct = (this.blueScore / total) * 100;
    const redBar = document.getElementById('red-bar');
    const blueBar = document.getElementById('blue-bar');
    if (redBar) redBar.style.width = `${redPct}%`;
    if (blueBar) blueBar.style.width = `${bluePct}%`;
  }

  _animateScore(el, target, animate) {
    if (!animate) {
      el.textContent = target;
      return;
    }
    const current = parseInt(el.textContent) || 0;
    if (current === target) return;

    const diff = target - current;
    const steps = 12;
    let step = 0;

    const tick = () => {
      step++;
      const progress = step / steps;
      const eased = 1 - Math.pow(1 - progress, 3);
      el.textContent = Math.round(current + diff * eased);
      if (step < steps) {
        requestAnimationFrame(tick);
      } else {
        el.textContent = target;
        el.classList.add('score-pop');
        setTimeout(() => el.classList.remove('score-pop'), 300);
      }
    };
    requestAnimationFrame(tick);
  }

  _updatePhase(phase) {
    this.phaseEl.textContent = phase;
    this.phaseEl.className = 'phase-value phase-' + phase.toLowerCase();
  }

  _updateKillChain() {
    KILL_CHAIN_STAGES.forEach(stage => {
      const el = document.getElementById(`kc-${stage.id}`);
      if (el && this.killChainReached.has(stage.id)) {
        el.classList.add('reached');
      }
    });
  }

  _resetKillChain() {
    KILL_CHAIN_STAGES.forEach(stage => {
      const el = document.getElementById(`kc-${stage.id}`);
      if (el) el.classList.remove('reached');
    });
  }

  _showConclusion() {
    this.isComplete = true;
    this.isPlaying = false;
    this.playBtn.innerHTML = '<span class="btn-icon">&#8635;</span> Replay';
    this.playBtn.classList.remove('playing');

    this._updatePhase(GAME_PHASES.CONCLUSION);
    this.turnEl.textContent = 'GAME OVER';

    // Show winner banner
    const banner = document.getElementById('conclusion-banner');
    if (banner) {
      banner.classList.add('visible');
    }

    // Trigger narrative section reveal
    const narrativeSection = document.getElementById('narrative');
    if (narrativeSection) {
      narrativeSection.classList.add('revealed');
      this._typeNarrative();
    }
  }

  _typeNarrative() {
    const container = document.getElementById('narrative-text');
    if (!container) return;
    container.textContent = '';
    let i = 0;
    const text = NARRATIVE_SUMMARY;
    const interval = 8 / this.speed;

    const type = () => {
      if (i < text.length) {
        const chunk = Math.min(i + 3, text.length);
        container.textContent = text.substring(0, chunk);
        i = chunk;
        container.scrollTop = container.scrollHeight;
        setTimeout(type, interval);
      }
    };
    type();
  }
}
