from pathlib import Path

from streamlit.testing.v1 import AppTest


APP = Path(__file__).resolve().parents[1] / "app" / "monitoramento_v3.py"


def test_dashboard_abre_snapshot_sem_excecao():
    app = AppTest.from_file(str(APP)).run(timeout=15)

    assert not app.exception


def test_dashboard_permite_selecionar_2020_h2():
    app = AppTest.from_file(str(APP)).run(timeout=15)
    app.radio[0].set_value("2020-H2").run(timeout=15)

    assert app.radio[0].value == "2020-H2"


def test_dashboard_explica_restricao_de_pesquisa():
    app = AppTest.from_file(str(APP)).run(timeout=15)
    textos = " ".join(item.value for item in app.markdown)

    assert "não libera uso operacional" in textos


def test_dashboard_ensina_a_ler_os_sinais_sem_jargao():
    app = AppTest.from_file(str(APP)).run(timeout=15)
    textos = " ".join(item.value for item in app.markdown)

    assert "Como ler este relatório" in textos
    assert "comece pela decisão" in textos.lower()


def test_dashboard_explica_o_caminho_ate_o_gestor():
    app = AppTest.from_file(str(APP)).run(timeout=15)
    textos = " ".join(item.value for item in app.markdown)

    assert "Como esta informação chega a quem decide" in textos
    assert "Snapshot agregado" in textos
