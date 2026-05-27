from .currency import avg_currency
from .models import assert_currency
from .job import Job

import pandas as pd
import matplotlib.pyplot as plt

ANNOTATION_STYLE: dict = dict(fontsize=8, horizontalalignment='right', verticalalignment='center', xytext=(0,0), textcoords='offset points', bbox=dict(boxstyle='round', facecolor='white', alpha=0.8))

def summarize_offers(offer_groups: dict[str, list[Job]], years: int = 4):
    df = pd.DataFrame(columns=["Company", "Offer", "Cumulative Compensation (Low)", "Cumulative Compensation (Mid)", "Cumulative Compensation (High)", f"Share Price after {years} years", f"Valuation after {years} years"])
   
    def get_data(group: str, offers: list[Job]):
        low_ball = offers[0].cumulative_value_after(years)
        high_ball = offers[-1].cumulative_value_after(years)
        low_ball, high_ball = min(low_ball, high_ball), max(low_ball, high_ball)
        mid_ball = avg_currency([offer.cumulative_value_after(years) for offer in offers])
        share_price = avg_currency([offer.company.share_price_after(years) for offer in offers])
        valuation = avg_currency([offer.company.valuation_after(years) for offer in offers])

        return (offers[0].company.name, group, low_ball, assert_currency(mid_ball), high_ball, share_price, valuation)

    df = pd.DataFrame(list(get_data(group, offers) for group, offers in offer_groups.items()), columns=df.columns)
    df.sort_values(by="Cumulative Compensation (Mid)", ascending=False, inplace=True)
    
    return df

def render_cumulative_compensation(offer_groups: dict[str, list[Job]], years: int = 4):
    fig, comp = plt.subplots(figsize=(12, 8))

    comp.set_title("Cumulative Compensation")
    comp.set_ylabel("$ gross")

    for group, offers in offer_groups.items():
        if len(offers) == 1:
            comp.plot(list(range(0, years + 1)), list(val.value for _, val in zip(range(years+1), offers[0].cumulative_value())), label=group, linestyle='-')
            for year, val in zip(range(0, years), offers[0].cumulative_value()):
                comp.annotate(f"{val}", xy=(year, val.value), **ANNOTATION_STYLE)
        else:
            comp.fill_between(
                list(range(0, years + 1)),
                y1=list(val.value for _, val in zip(range(years+1), offers[0].cumulative_value())), # pyright: ignore[reportArgumentType]
                y2=list(val.value for _, val in zip(range(years+1), offers[-1].cumulative_value())), # pyright: ignore[reportArgumentType]
                alpha=0.3)
            
            for year in range(years):
                mid_ball = avg_currency([offer.cumulative_value_after(year) for offer in offers])
                comp.annotate(f"{mid_ball}", xy=(year, mid_ball.value), **ANNOTATION_STYLE)


        low_ball = offers[0].cumulative_value_after(years)
        high_ball = offers[-1].cumulative_value_after(years)
        low_ball, high_ball = min(low_ball, high_ball), max(low_ball, high_ball)
        mid_ball = avg_currency([offer.cumulative_value_after(years) for offer in offers])
        valuation = avg_currency([offer.company.valuation_after(years) for offer in offers])

        if low_ball == high_ball:
            comp.annotate(f"{group}\n{low_ball}\n{valuation}", xy=(years, mid_ball.value), **ANNOTATION_STYLE)
        else:
            comp.annotate(f"{group}\n{low_ball} - {high_ball}\n{valuation}", xy=(years, mid_ball.value), **ANNOTATION_STYLE)

    return fig, comp


def render_annual_compensation(offer_groups: dict[str, list[Job]], years: int = 4):
    fig, comp = plt.subplots(figsize=(12, 8))

    comp.set_title("Annual Compensation")
    comp.set_ylabel("$ gross")

    for group, offers in offer_groups.items():
        if len(offers) == 1:
            comp.plot(list(range(0, years + 1)), list(val.value for _, val in zip(range(years+1), offers[0].annual_compensation())), label=group, linestyle='-')
            for year, val in zip(range(0, years), offers[0].annual_compensation()):
                comp.annotate(f"{val}", xy=(year, val.value), **ANNOTATION_STYLE)
        else:
            comp.fill_between(
                list(range(0, years + 1)),
                list(val.value for _, val in zip(range(years+1), offers[0].annual_compensation())), # pyright: ignore[reportArgumentType]
                list(val.value for _, val in zip(range(years+1), offers[-1].annual_compensation())), # pyright: ignore[reportArgumentType]
                alpha=0.3)
            
            for year in range(0, years):
                mid_ball = avg_currency([offer.annual_compensation_after(year) for offer in offers])
                comp.annotate(f"{mid_ball}", xy=(year, mid_ball.value), **ANNOTATION_STYLE)

        low_ball = offers[0].annual_compensation_after(years)
        high_ball = offers[-1].annual_compensation_after(years)
        low_ball, high_ball = min(low_ball, high_ball), max(low_ball, high_ball)
        mid_ball = offers[1].annual_compensation_after(years) if len(offers) > 2 else assert_currency((high_ball + low_ball)/2)

        valuation_suffix = ""

        if low_ball == high_ball:
            comp.annotate(f"{group}\n{low_ball}{valuation_suffix}", xy=(years, mid_ball.value), **ANNOTATION_STYLE)
        else:
            comp.annotate(f"{group}\n{low_ball} - {high_ball}{valuation_suffix}", xy=(years, mid_ball.value), **ANNOTATION_STYLE)

    return fig, comp

