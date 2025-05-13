from flask import Flask, render_template, request, jsonify
import pandas as pd
import plotly.express as px
import plotly.io as pio
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import seaborn as sns
import base64
from io import BytesIO


app = Flask(__name__)

# Load and clean your dataframe
df = pd.read_csv('./data/Coffee Shop Sales.csv', low_memory=False)
df.columns = df.columns.str.strip().str.lower()
df['date'] = pd.to_datetime(df['transaction_date'] + '-' + df['transaction_time'], format="mixed")
df.drop(['transaction_date', 'transaction_time'], axis=1, inplace=True)
df.set_index('date', inplace=True)

# Additional features
df['month'] = df.index.month
df['is_weekend'] = df.index.weekday >= 5
df['revenue'] = df['transaction_qty'] * df['unit_price']
df['hour'] = df.index.hour
df['day'] = df.index.day
df['day_name'] = df.index.day_name()

month_map = {
    1: "January", 2: "February", 3: "March",
    4: "April", 5: "May", 6: "June"
}

# Unified plot generator
def generate_plot(df, x, y, title, plot_type, x_label, y_label):
    if plot_type in ['line', 'bar']:
        fig_func = px.line if plot_type == 'line' else px.bar
        fig = fig_func(df, x=x, y=y, title=title, labels={x: x_label, y: y_label})
        fig.update_layout(
            margin=dict(l=0, r=0, t=40, b=0),
            autosize=True
            )
        return pio.to_html(fig, full_html=False, config={'responsive': True})
    elif plot_type in ['hist', 'kde']:
        plt.figure(figsize=(6, 2.5))
        if plot_type == 'hist':
            sns.histplot(df[y], kde=False)
        else:
            sns.kdeplot(df[y], fill=True)
        plt.title(title)
        plt.xlabel(y_label)
        plt.tight_layout()

        buf = BytesIO()
        plt.savefig(buf, format='png')
        plt.close()
        buf.seek(0)
        img_base64 = base64.b64encode(buf.read()).decode('utf-8')
        return f'<img src="data:image/png;base64,{img_base64}"/>'
    else:
        return ""

@app.route("/")
def index():
    return render_template("index.html", months=month_map)

@app.route("/get_data", methods=["POST"])
def get_data():
    data = request.json
    month = int(data["month"])
    plot_type = data.get("plotType", "all")
    sales_plot = data.get("sales_plot", "line")
    orders_plot = data.get("orders_plot", "line")
    quantity_plot = data.get("quantity_plot", "line")

    month_data = df[df["month"] == month].copy()
    response = {}

    # Top 3 charts (dynamic type)
    daily_metrics = month_data.resample("D").agg({
        "revenue": "sum",
        "transaction_id": "count",
        "transaction_qty": "sum"
    }).reset_index()

    response["sales_line"] = generate_plot(
        daily_metrics, x="date", y="revenue",
        title="Daily Revenue",
        plot_type=sales_plot,
        x_label="Date", y_label="Revenue"
    )

    response["orders_line"] = generate_plot(
        daily_metrics, x="date", y="transaction_id",
        title="Total Orders",
        plot_type=orders_plot,
        x_label="Date", y_label="Orders"
    )

    response["quantity_line"] = generate_plot(
        daily_metrics, x="date", y="transaction_qty",
        title="Quantity Sold",
        plot_type=quantity_plot,
        x_label="Date", y_label="Quantity"
    )

    # Pie chart (weekday vs weekend)
    if plot_type in ["all", "pie"]:
        pie_data = month_data.groupby("is_weekend")["revenue"].sum().reset_index()
        pie_data["label"] = pie_data["is_weekend"].map({False: "Weekday", True: "Weekend"})
        fig_pie = px.pie(pie_data, values="revenue", names="label",
                         title=f"{month_map[month]}: Weekday vs Weekend Revenue",
                         color_discrete_sequence=["#4c72b0", "#dd8452"])
        response["pie_chart"] = pio.to_html(fig_pie, full_html=False, config={'responsive': True})
    else:
        response["pie_chart"] = ""

    # Horizontal bar chart by store
    if plot_type in ["all", "bar"]:
        bar_data = month_data.groupby("store_location")["revenue"].sum().reset_index().sort_values(by="revenue")
        fig_bar = px.bar(bar_data, x="revenue", y="store_location", orientation='h',
                         title=f"{month_map[month]}: Sales by Store",
                         labels={"revenue": "Revenue", "store_location": "Store Location"},
                         color_discrete_sequence=["skyblue"])
        response["bar_chart"] = pio.to_html(fig_bar, full_html=False, config={'responsive': True})
    else:
        response["bar_chart"] = ""

    # Daily bar chart
    if plot_type in ["all", "daily"]:
        daily_sales = month_data.groupby("day")["revenue"].sum().reset_index()
        fig_daily = px.bar(daily_sales, x="day", y="revenue",
                           title=f"{month_map[month]}: Daily Sales",
                           labels={"day": "Day of Month", "revenue": "Revenue"},
                           color_discrete_sequence=["#a1dab4"])
        response["daily_sales_chart"] = pio.to_html(fig_daily, full_html=False, config={'responsive': True})
    else:
        response["daily_sales_chart"] = ""

    # Footfall (always displayed)
    hourly_footfall = (
        month_data.groupby([month_data.index.date, month_data.index.hour])["transaction_id"]
        .count()
        .reset_index(name="count")
    )
    hourly_footfall.columns = ["date", "hour", "count"]
    avg_footfall = hourly_footfall.groupby("hour")["count"].mean().reset_index()

    fig_footfall = px.line(
        avg_footfall,
        x="hour",
        y="count",
        title=f"{month_map.get(month, 'All Months')}: Average Hourly Footfall",
        labels={"hour": "Hour of Day", "count": "Avg. Footfall"},
        markers=True,
        line_shape="spline"
    )
    fig_footfall.update_layout(
            margin=dict(l=0, r=0, t=40, b=0),
            autosize=True
            )
    response["footfall_chart"] = pio.to_html(fig_footfall, full_html=False, config={'responsive': True})

    return jsonify(response)
