"""Package des vues de l'app pv-dashboard.

Chaque vue herite de BaseView et implemente populate(period). Les helpers
partages (formatage, selection de periode) sont dans _helpers.py.
"""
from views._base import BaseView
from views._helpers import (
    MOIS_TOUS,
    PERIOD_ALL,
    annee_de_periode,
    bornes_annee_oa,
    filter_period,
    fmt_date_fr,
    fmt_eur,
    fmt_kwc,
    fmt_kwh,
    fmt_pct,
    label_mois_fr,
    options_annees,
    options_mois,
    pas_graphique,
    period_options,
    periode_voisine,
)
from views.accounts import AccountsView
from views.aide import AideView
from views.categories import CategoriesView
from views.comparaison import ComparaisonView
from views.dashboard import DashboardView
from views.oa import OAView
from views.octopus_edf import OctopusEdfView
from views.saisie import SaisieView
from views.settings import SettingsView
from views.stats import StatsView
from views.transactions import TransactionsView
from views.tva import TvaView

__all__ = [
    "BaseView",
    "MOIS_TOUS",
    "PERIOD_ALL",
    "annee_de_periode",
    "bornes_annee_oa",
    "filter_period",
    "fmt_date_fr",
    "fmt_eur",
    "fmt_kwc",
    "fmt_kwh",
    "fmt_pct",
    "label_mois_fr",
    "options_annees",
    "options_mois",
    "pas_graphique",
    "period_options",
    "periode_voisine",
    # Vues
    "AccountsView",
    "AideView",
    "CategoriesView",
    "ComparaisonView",
    "DashboardView",
    "OAView",
    "OctopusEdfView",
    "SaisieView",
    "SettingsView",
    "StatsView",
    "TransactionsView",
    "TvaView",
]
