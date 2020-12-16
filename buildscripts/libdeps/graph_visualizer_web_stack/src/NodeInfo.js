import React from 'react';
import { connect } from "react-redux";
import { FixedSizeList } from 'react-window';
import { AutoSizer } from 'react-virtualized';
import { makeStyles } from '@material-ui/core/styles';
import List from '@material-ui/core/List';
import ListItem from '@material-ui/core/ListItem';
import ListItemText from '@material-ui/core/ListItemText';
import Collapse from '@material-ui/core/Collapse';
import ExpandLess from '@material-ui/icons/ExpandLess';
import ExpandMore from '@material-ui/icons/ExpandMore';
import Paper from '@material-ui/core/Paper';

import { getNodeInfos } from './redux/store';
import { updateCheckbox } from './redux/nodes';
import { socket } from './connect';
import theme from './theme';

import OverflowTooltip from './OverflowTooltip';

const NodeInfo = ({nodeInfos, updateCheckbox, node, width}) => {

  const useStyles = makeStyles((theme) => ({
    root: {
      width: '100%',
      maxWidth: width,
      backgroundColor: theme.palette.background.paper,
    },
    nested: {
      paddingLeft: theme.spacing(4),
    },
    listItem: {
      width: width
    }
  }));

  const rowHeight = 30;
  const classes = useStyles();
  const [openDependers, setOpenDependers] = React.useState(false);
  const [openDependencies, setOpenDependencies] = React.useState(false);
  const [openNodeAttribs, setOpenNodeAttribs] = React.useState(false);

  const [nodeInfo, setNodeInfo] = React.useState({
      id: 0,
      node: 'test/test.so',
      name: 'test',
      attribs: [
        {name: 'test', value: 'test'}
      ],
      dependers: [
        {node: 'test/test3.so', symbols: []}
      ],
      dependencies: [
        {node: 'test/test2.so', symbols: []}
      ]
    });

  React.useEffect(() => {
    setNodeInfo(nodeInfos.filter(nodeInfo => nodeInfo.node == node.node)[0]);
  }, [nodeInfos]);

  function renderAttribRow({ index, style, data }) {

    return (
      <ListItem button style={style} key={index}>
        <OverflowTooltip mr={1} value={data[index].name} text={String(data[index].name) + ": "}/>
        <OverflowTooltip value={String(data[index].value)} text={String(data[index].value)}/>
      </ListItem>
    );
  }

  function renderNodeRow({ index, style, data }) {

    return (
      <ListItem button style={style} key={index} onClick={(event) => {
        updateCheckbox({ node: data[index].node, value: 'flip'});
        socket.emit('row_selected', {data: {node: data[index].node, name: data[index].name}, isSelected: 'flip'});}}
      >
        <OverflowTooltip mr={1} value={data[index].node} text={data[index].node}/>
      </ListItem>
    );
  }

  function listHeight(numItems){
    const size = numItems * rowHeight;
    if (size > 350){
      return 350;
    }
    return size;
  }

  if (nodeInfo == undefined){
    return '';
  }
  return (
    <List
      component="nav"
      aria-labelledby="nested-list-subheader"
      className={classes.root}
    >
      <Paper elevation={3} style={{backgroundColor: 'rgba(0, 0, 0, .03)'}}>
        <ListItem button>
          <ListItemText primary={nodeInfo.node} />
        </ListItem>
        <ListItem button>
          <ListItemText primary={nodeInfo.name} />
        </ListItem>

        <ListItem button onClick={() => setOpenNodeAttribs(!openNodeAttribs)}>
          <ListItemText primary="Attributes" />
          {openNodeAttribs ? <ExpandLess /> : <ExpandMore />}
        </ListItem>
        <Collapse in={openNodeAttribs} timeout="auto" unmountOnExit>

          <Paper elevation={2} style={{width: '100%',backgroundColor: theme.palette.background.paper}}>
            <AutoSizer disableHeight={true}>
              {({ height, width }) => (
                <FixedSizeList
                  height={listHeight(nodeInfo.attribs.length)}
                  width={width}
                  itemSize={rowHeight}
                  itemCount={nodeInfo.attribs.length}
                  itemData={nodeInfo.attribs}
                >
                  {renderAttribRow}
                </FixedSizeList>
              )}
            </AutoSizer>
          </Paper>
        </Collapse>

        <ListItem button onClick={() => setOpenDependers(!openDependers)}>
          <ListItemText primary="Dependers" />
          {openDependers ? <ExpandLess /> : <ExpandMore />}
        </ListItem>
        <Collapse in={openDependers} timeout="auto" unmountOnExit>
          <Paper elevation={4}>
            <AutoSizer disableHeight={true}>
              {({ height, width }) => (
                <FixedSizeList
                  height={listHeight(nodeInfo.dependers.length)}
                  width={width}
                  itemSize={rowHeight}
                  itemCount={nodeInfo.dependers.length}
                  itemData={nodeInfo.dependers}
                >
                  {renderNodeRow}
                </FixedSizeList>
              )}
            </AutoSizer>
          </Paper>
        </Collapse>

        <ListItem button onClick={() => setOpenDependencies(!openDependencies)}>
          <ListItemText primary="Dependencies" />
          {openDependencies ? <ExpandLess /> : <ExpandMore />}
        </ListItem>
        <Collapse in={openDependencies} timeout="auto" unmountOnExit>
          <Paper elevation={4}>
            <AutoSizer disableHeight={true}>
              {({ height, width }) => (
                <FixedSizeList
                  height={listHeight(nodeInfo.dependencies.length)}
                  width={width}
                  itemSize={rowHeight}
                  itemCount={nodeInfo.dependencies.length}
                  itemData={nodeInfo.dependencies}
                >
                  {renderNodeRow}
                </FixedSizeList>
              )}
            </AutoSizer>
          </Paper>
        </Collapse>
      </Paper>
    </List>
  );
};

export default connect(getNodeInfos, {updateCheckbox})(NodeInfo);
