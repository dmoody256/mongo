import * as React from 'react';
import { DataGrid } from '@material-ui/data-grid';
import { AutoSizer } from 'react-virtualized';
import { connect } from "react-redux";
import { getCounts } from './redux/store';

const columns = [
  { id: 'ID', field: 'type', headerName: 'Count Type', width:200 },
  { field: 'value', headerName: 'Value', width:200  },
];

const GraphInfo = ({counts, datawidth})=> {

  return (
    <div style={{width:'100%'}}>
    <AutoSizer disableHeight={true}>
          {({ height, width }) => (
      <div style={{height: String((counts.length+2) * 30) +'px', width:width}}>
      <DataGrid
        rows={counts}
        columns={columns}
        rowHeight={30}
        headerHeight={35}
        hideFooter={true}
      /></div>
      )}</AutoSizer>
    </div>
  );
};

export default connect(getCounts, {})(GraphInfo);
