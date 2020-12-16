import React, { useRef, useEffect, useState } from 'react';
import Tooltip from '@material-ui/core/Tooltip';
import Fade from '@material-ui/core/Fade';
import Box from '@material-ui/core/Box';

const OverflowTip = props => {

  const textElementRef = useRef(null);

  const compareSize = () => {
    const compare =
      textElementRef.current.scrollWidth > textElementRef.current.offsetWidth;
    setHover(compare);
  };

  useEffect(() => {
    compareSize();
    window.addEventListener('resize', compareSize);
  }, [props]);


  useEffect(() => () => {
    window.removeEventListener('resize', compareSize);
  }, []);


  const [hoverStatus, setHover] = useState(false);

  return (
    <Tooltip
      title={props.value}
      interactive
      disableHoverListener={!hoverStatus}
      style={{fontSize: '2em'}}
      enterDelay={500} TransitionComponent={Fade}
    >
      <Box
        ref={textElementRef}
        mr={props.mr}
        style={{
          whiteSpace: 'nowrap',
          overflow: 'hidden',
          textOverflow: 'ellipsis'
        }}
      >
        {props.text}
      </Box>
    </Tooltip>
  );
};

export default OverflowTip;