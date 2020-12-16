import React from 'react';
import { connect } from "react-redux";
import LoadingButton from '@material-ui/lab/LoadingButton';
import GitIcon from '@material-ui/icons/GitHub';
import { makeStyles,  } from '@material-ui/core/styles';
import { green, grey } from '@material-ui/core/colors';

import { socket } from './connect';
import { getGraphFiles } from './redux/store';
import { setLoading } from './redux/loading';

const useStyles = makeStyles((theme) => ({
  selected: {
    color: theme.palette.getContrastText(green[500]),
    backgroundColor: green[500],
    '&:hover': {
      backgroundColor: green[600],
    },
    '&:active': {
      backgroundColor: green[700],
    },
  },
  unselected: {
    color: theme.palette.getContrastText(grey[100]),
    backgroundColor: grey[100],
    '&:hover': {
      backgroundColor: grey[400],
    },
    '&:active': {
      backgroundColor: grey[400],
    },
  },
}));

const GitHashButton = ({loading, graphFiles, setLoading, text, file}) => {

  const [selected, setSelected] = React.useState(false);
  const [selfLoading, setSelfLoading] = React.useState(false);
  const [firstLoad, setFirstLoad] = React.useState(true);

  const classes = useStyles();

  function handleClick() {
    setSelfLoading(true);
    setLoading(true);
    socket.emit("git_hash_selected", {'hash':text, 'file': file, 'selected':true});
  }

  React.useEffect(() => {
    const selectedGraphFile = graphFiles.filter(graphFile => graphFile.git == text);
    setSelected(selectedGraphFile[0].selected);

    if (firstLoad && graphFiles.length > 0){
      if (graphFiles[0]['git'] == text){
        handleClick();
      }
      setFirstLoad(false);
    }
  }, [graphFiles]);

  React.useEffect(() => {
    if (!loading){
      setSelfLoading(false);
    }
  }, [loading]);

  return (
    <LoadingButton
      pending={selfLoading}
      pendingPosition="start"
      startIcon={<GitIcon />}
      variant="contained" color="primary"
      className={`${selected ? classes.selected : classes.unselected}`}
      onClick={handleClick}
    >
      {text}
    </LoadingButton>
  );
};

export default connect(getGraphFiles, {setLoading})(GitHashButton);

