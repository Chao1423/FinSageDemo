from tools import *

data = StockTools(['AAPL'])
output_df = data.data_for_plotting()

fig = px.line(output_df, x='Date', y=[col for col in output_df.columns if col != 'Date'], title='Stock Data Over Time', labels={'value': str(['column']), 'variable': 'Stock Ticker'})
fig.show()
print(fig.to_json())