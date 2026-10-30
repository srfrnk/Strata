#compdef strata

_strata() {
    local -a commands
    commands=(
        'start:Start Strata service container in background'
        'stop:Stop Strata service container'
        'restart:Restart Strata service container'
        'status:Check status of container and service API'
        'build:Build or rebuild Strata Docker image'
        'open:Open Strata Admin Web UI in default browser'
        'monitor:Open the chat page Monitor tab (#monitor)'
        'api-monitor:Open the standalone Strata API Monitor page (/api-monitor)'
        'config:Codified configuration of Crush, Goose, Pi, and Hermes'
        'crush:Launch Crush against Strata'
        'goose:Launch Goose against Strata'
        'pi:Launch Pi against Strata'
        'hermes:Launch Hermes against Strata'
        'completion:Generate or install shell completion (bash/zsh)'
    )

    _arguments -C \
        '1: :->command' \
        '*:: :->args'

    case $state in
        command)
            _describe -t commands 'strata commands' commands
            ;;
        args)
            case $line[1] in
                completion)
                    local -a shells
                    shells=('bash:Generate Bash completion script' 'zsh:Generate Zsh completion script' 'install:Install completions to ~/.bashrc and ~/.zshrc')
                    _describe -t shells 'shell' shells
                    ;;
                monitor|api-monitor)
                    local -a monitor_opts
                    monitor_opts=('--enable:Turn the API request monitor on before opening it')
                    _describe -t monitor_opts 'monitor options' monitor_opts
                    ;;
                crush|goose|pi|hermes)
                    _files
                    ;;
            esac
            ;;
    esac
}

compdef _strata strata 2>/dev/null || true
