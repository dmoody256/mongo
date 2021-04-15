import React from "react";
import { connect } from "react-redux";
import { FixedSizeList } from "react-window";
import { AutoSizer } from "react-virtualized";
import SplitPane from "react-split-pane";
import { makeStyles , withStyles} from "@material-ui/core/styles";
import List from "@material-ui/core/List";
import ListItem from "@material-ui/core/ListItem";
import ListItemText from "@material-ui/core/ListItemText";
import Collapse from "@material-ui/core/Collapse";
import Grow from "@material-ui/core/Grow";
import ExpandLess from "@material-ui/icons/ExpandLess";
import ExpandMore from "@material-ui/icons/ExpandMore";
import Paper from "@material-ui/core/Paper";
import Typography from "@material-ui/core/Typography";
import Box from "@material-ui/core/Box";
import ExpandMoreIcon from "@material-ui/icons/ExpandMore";
import MuiAccordion from "@material-ui/core/Accordion";
import MuiAccordionSummary from "@material-ui/core/AccordionSummary";
import MuiAccordionDetails from "@material-ui/core/AccordionDetails";
import { socket } from "./connect";

import { getSelected } from "./redux/store";
import { selectedGraphPaths, setSelectedPath } from "./redux/graphPaths";


import theme from "./theme";

import OverflowTooltip from "./OverflowTooltip";
import DataGrid from "./DataGrid";

const columns = [
  { dataKey: "check", label: "Selected", width: 70 },
  { dataKey: "name", label: "Name", width: 200 },
  { id: "ID", dataKey: "node", label: "Node", width: 200 },
];

const useStyles = makeStyles((theme) => ({
  root: {
    width: "100%",
  },
  heading: {
    fontSize: theme.typography.pxToRem(15),
    fontWeight: theme.typography.fontWeightRegular,
  },
}));

const Accordion = withStyles({
  root: {
    border: "1px solid rgba(0, 0, 0, .125)",
    boxShadow: "none",
    "&:not(:last-child)": {
      borderBottom: 0,
    },
    "&:before": {
      display: "none",
    },
    "&$expanded": {
      margin: "auto",
    },
  },
  expanded: {},
})(MuiAccordion);

const AccordionSummary = withStyles({
  root: {
    backgroundColor: "rgba(0, 0, 0, .03)",
    borderBottom: "1px solid rgba(0, 0, 0, .125)",
    marginBottom: -1,
    minHeight: 56,
    "&$expanded": {
      minHeight: 56,
    },
  },
  content: {
    "&$expanded": {
      margin: "12px 0",
    },
  },
  expanded: {},
})(MuiAccordionSummary);

const AccordionDetails = withStyles((theme) => ({
  root: {
    padding: theme.spacing(2),
  },
}))(MuiAccordionDetails);

const GraphPaths = ({ selectedNodes, graphPaths, setSelectedPath, width }) => {
    const [fromNode, setFromNode] = React.useState('');
    const [toNode, setToNode] = React.useState('');
    const [fromNodeId, setFromNodeId] = React.useState(0);
    const [toNodeId, setToNodeId] = React.useState(0);
    const [fromNodeExpanded, setFromNodeExpanded] = React.useState(false);
    const [toNodeExpanded, setToNodeExpanded] = React.useState(false);
    const [paneSize, setPaneSize] = React.useState('50%');
  const useStyles = makeStyles((theme) => ({
    root: {
      width: "100%",
      maxWidth: width,
      backgroundColor: theme.palette.background.paper,
    },
    nested: {
      paddingLeft: theme.spacing(4),
    },
    listItem: {
      width: width,
    },
  }));

  const rowHeight = 25;
  const classes = useStyles();

  function renderAttribRow({ index, style, data }) {
    return (
      <ListItem button style={style} key={index}>
          <ListItemText primary={data[index].node} />
      </ListItem>

    );
  }



  function toNodeRow({ index, style, data }) {
    return (
      <ListItem button style={style} key={index} onClick={() => {

            setToNode(data[index].name);
            setToNodeId(index);
            setToNodeExpanded(false);
            setPaneSize('50%');
            if (fromNode != '' && data[fromNodeId]){
                const nodes = {fromNode: data[fromNodeId].node, toNode: data[index].node};
                //selectedGraphPathNodes(nodes);
                socket.emit("receive_graph_paths", nodes);
            }

          }
        } >
          <ListItemText primary={data[index].name} />
      </ListItem>

    );
  }


  function fromNodeRow({ index, style, data }) {
    return (
      <ListItem button style={style} key={index} onClick={() => {

            setFromNode(data[index].name);
            setFromNodeId(index);
            setFromNodeExpanded(false);
            setPaneSize('50%');

            if (toNode != '' && data[toNodeId]){
                const nodes = {fromNode: data[index].node, toNode: data[toNodeId].node};
                //selectedGraphPathNodes(nodes);
                socket.emit("receive_graph_paths", nodes);
            }
          }
        }  >
          <ListItemText primary={data[index].name} />
      </ListItem>

    );
  }

    function pathRow({ index, style, data }) {
    return (
      <ListItem button style={style} key={index} onClick={() => {
          setSelectedPath(index);

      }}>
          <ListItemText primary={"Hops: " + (data[index].length-1).toString()} />
      </ListItem>

    );
  }

  function renderNodeRow({ index, style, data }) {
    return (
      <ListItem style={style} key={index}>
        <OverflowTooltip
          button
          name={data[index].name}
          value={data[index].node}
          text={data[index].node}
        />
      </ListItem>
    );
  }

  function listHeight(numItems, minHeight, maxHeight) {
    const size = numItems * rowHeight;
    if (size > maxHeight) {
      return maxHeight;
    }
    if (size < minHeight){
       return minHeight;
    }
    return size;
  }

  function handleCheckBoxes(rowIndex, event) {
    socket.emit("row_selected", {
      data: { node: nodes[rowIndex].node, name: nodes[rowIndex].name },
      isSelected: event.target.checked,
    });
  }

  function handleRowClick(event) {
    setFindNode(event.target.textContent);
  }

  const handleToChange = (panel) => (event, newExpanded) => {
    setPaneSize(newExpanded ? '0%' : '50%');
    setToNodeExpanded(newExpanded ? panel : false);
  };

  const handleFromChange = (panel) => (event, newExpanded) => {
    setPaneSize(newExpanded ? '100%' : '50%');
    setFromNodeExpanded(newExpanded ? panel : false);

  };

  return (
      <Paper elevation={3} style={{ backgroundColor: "rgba(0, 0, 0, .03)" }}>
          <SplitPane
            split="vertical"
            minSize={"50%"}

            size={paneSize}
            style={{ position: "relative" }}
            defaultSize={"50%"}
            pane1Style={{ height: "100%" }}
            pane2Style={{ height: "100%", width: "100%" }}
        >


          <Accordion expanded={fromNodeExpanded} onChange={handleFromChange(!fromNodeExpanded)}>
            <AccordionSummary
              expandIcon={<ExpandMoreIcon />}
              aria-controls="panel1a-content"
              id="panel1a-header"
            >
              <Box style={{display: "flex", flexDirection: "column"}}>
              <Typography className={classes.heading}>From Node:</Typography>
              <Typography className={classes.heading}>{fromNode}</Typography>
              </Box>
            </AccordionSummary>
            <AccordionDetails>
              <FixedSizeList
                  height={listHeight(selectedNodes.length, 100, 200)}
                  width={width}
                  itemSize={rowHeight}
                  itemCount={selectedNodes.length}
                  itemData={selectedNodes}
                >
                  {fromNodeRow}
                </FixedSizeList>
            </AccordionDetails>
          </Accordion>

          <Accordion expanded={toNodeExpanded} onChange={handleToChange(!toNodeExpanded)} >
            <AccordionSummary
              expandIcon={<ExpandMoreIcon />}
              aria-controls="panel1a-content"
              id="panel1a-header"
            >
              <Box style={{display: "flex", flexDirection: "column"}}>
                <Typography className={classes.heading}>To Node:</Typography>
                <Typography className={classes.heading}>{toNode}</Typography>
              </Box>
            </AccordionSummary>
            <AccordionDetails >
              <FixedSizeList
                  height={listHeight(selectedNodes.length, 100, 200)}
                  width={width}
                  itemSize={rowHeight}
                  itemCount={selectedNodes.length}
                  itemData={selectedNodes}
                >
                  {toNodeRow}
                </FixedSizeList>
            </AccordionDetails>
          </Accordion>

        </SplitPane>
        <Paper elevation={2} style={{ backgroundColor: "rgba(0, 0, 0, .03)"}}>
        <Typography className={classes.heading} style={{ margin: '10px' }}>Num Paths: {graphPaths.paths.length} </Typography>
        </Paper>
        <FixedSizeList
            height={listHeight(graphPaths.paths.length, 100, 200)}
            width={width}
            itemSize={rowHeight}
            itemCount={graphPaths.paths.length}
            itemData={graphPaths.paths}
            style={{ margin:'10px' }}
        >
            {pathRow}
        </FixedSizeList>

      </Paper>

  );
};

export default connect(getSelected, {selectedGraphPaths, setSelectedPath})(GraphPaths);
