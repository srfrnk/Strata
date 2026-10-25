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
        'monitor:Open Strata API Monitor in default browser'
        'config:Codified configuration of Crush, Goose, and Pi'
        'crush:Launch Crush against Strata'
        'goose:Launch Goose against Strata'
        'pi:Launch Pi against Strata'
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
                crush|goose|pi)
                    _files
                    ;;
            esac
            ;;
    esac
}

compdef _strata strata 2>/dev/null || true
