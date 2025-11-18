document.addEventListener('DOMContentLoaded', function () {
const forms = document.querySelectorAll('.form-excluir-func');

forms.forEach(function (form) {
    form.addEventListener('submit', function (e) {
    e.preventDefault();  // impede envio automático

    const nome = form.dataset.nome || 'este funcionário';

    const senha = prompt(
        `Para excluir ${nome}, digite a senha de administrador:`
    );

    // Se o usuário apertar "Cancelar"
    if (senha === null) {
        return;
    }

    if (senha.trim() === '') {
        alert('Senha não pode ser vazia.');
        return;
    }

    // Preenche o campo hidden com a senha digitada
    form.querySelector('input[name="senha_confirmacao"]').value = senha;

    // Agora sim envia o formulário
    form.submit();
    });
});
});