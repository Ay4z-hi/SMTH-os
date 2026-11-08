# SMTH Core CLI
HISTFILE=~/.zsh_history; HISTSIZE=50000; SAVEHIST=50000
setopt HIST_IGNORE_DUPS SHARE_HISTORY AUTO_CD INTERACTIVE_COMMENTS
autoload -Uz compinit && compinit -q
zstyle ':completion:*' menu select
PROMPT='%F{cyan}●%f %F{white}%~%f %F{8}›%f '
RPROMPT='%F{8}%*%f'
alias ls='ls --color=auto' ll='ls -lah' vm='smth-vm run' open='smth-open'
[ -f /usr/share/zsh-autosuggestions/zsh-autosuggestions.zsh ] && . /usr/share/zsh-autosuggestions/zsh-autosuggestions.zsh
[ -f /usr/share/zsh-syntax-highlighting/zsh-syntax-highlighting.zsh ] && . /usr/share/zsh-syntax-highlighting/zsh-syntax-highlighting.zsh
[ -z "$SMTH_FETCHED" ] && command -v fastfetch >/dev/null && { export SMTH_FETCHED=1; fastfetch 2>/dev/null; }
