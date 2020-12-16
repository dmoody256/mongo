import { initialState } from './store';

export const graphFiles = (state = initialState, action) => {
  switch (action.type) {
    case 'setGraphFiles':
      return [...action.payload];
    case 'selectGraphFile':
       const arr2 = state.map((graphFile, index) => {
          if (action.payload.hash == graphFile.git){
              graphFile.selected = action.payload.selected;
          }
          else
          {
            graphFile.selected = false;
          }
          return graphFile;
        });
        return [...arr2];
    default:
      return state;
  }
};

export const setGraphFiles = graphFiles => ({
  type: 'setGraphFiles',
  payload: graphFiles
});

export const selectGraphFile = graphFiles => ({
  type: 'selectGraphFile',
  payload: graphFiles
});