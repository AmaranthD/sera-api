class ErroDePrompt(Exception):
    codigo = "erro_de_prompt"

    def __init__(self, mensagem: str) -> None:
        super().__init__(mensagem)
        self.mensagem = mensagem


class PersonalityInvalida(ErroDePrompt):
    codigo = "personality_invalida"


class PessoaInvalida(ErroDePrompt):
    codigo = "pessoa_invalida"


class AjusteInvalido(ErroDePrompt):
    codigo = "ajuste_invalido"


class MemoriaInvalida(ErroDePrompt):
    codigo = "memoria_invalida"


class ParametroInvalido(ErroDePrompt):
    codigo = "parametro_invalido"
