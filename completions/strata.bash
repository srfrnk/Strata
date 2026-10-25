# Bash completion for strata CLI

_strata_completion() {
    local cur prev words cword
    _init_completion || return

    local commands="start stop restart status build open monitor api-monitor config crush goose pi completion"

    if [[ ${cword} -eq 1 ]]; then
        COMPREPLY=( $(compgen -W "${commands}" -- "${cur}") )
        return 0
    fi

    case "${words[1]}" in
        completion)
            if [[ ${cword} -eq 2 ]]; then
                COMPREPLY=( $(compgen -W "bash zsh install" -- "${cur}") )
            fi
            ;;
        monitor|api-monitor)
            if [[ ${cur} == -* ]]; then
                COMPREPLY=( $(compgen -W "--enable" -- "${cur}") )
            fi
            ;;
        crush|goose|pi)
            # Default file completion for arguments passed to agents
            _filedir
            ;;
        *)
            ;;
    esac
}

complete -F _strata_completion strata
