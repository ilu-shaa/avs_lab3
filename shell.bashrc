# Loaded for each interactive Bash session in the teaching container.
[[ $- == *i* ]] || return

PS1='lab3 \w \$ '
printf '\nЛабораторная №3. Рабочие файлы: /work/current.\n\n'
