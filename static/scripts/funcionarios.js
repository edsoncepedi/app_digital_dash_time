document.addEventListener('DOMContentLoaded', function () {

    const forms = document.querySelectorAll('.form-excluir-func');

    forms.forEach(function (form) {

        form.addEventListener('submit', function (e) {

            e.preventDefault(); // impede envio automático

            const nome = form.dataset.nome || 'este funcionário';

            // Confirmação inicial
            const confirmar = confirm(
                "⚠️ ATENÇÃO\n\n" +
                `Deseja realmente excluir ${nome}?\n\n` +
                "TODOS os dados e sessões de trabalho serão apagados permanentemente."
            );

            if (!confirmar) {
                return;
            }

            // Pedido da senha
            const senha = prompt(
                `Para excluir ${nome}, digite a senha de administrador:`
            );

            if (senha === null) {
                return;
            }

            if (senha.trim() === '') {
                alert('Senha não pode ser vazia.');
                return;
            }

            // Preenche o campo hidden
            form.querySelector('input[name="senha_confirmacao"]').value = senha;

            // Agora envia o formulário
            form.submit();

        });

    });

});