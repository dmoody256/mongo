import { initialState } from './store';

export const nodes = (state = initialState, action) => {
  switch (action.type) {
    case 'addNode':
        var arr = Object.assign(state);
      return [...arr, action.payload];
    case 'setNodes':
      return [...action.payload];
    case 'updateSelected':
      var arr = Object.assign(state);
      arr[action.payload.index].selected = action.payload.value;
      return [...arr];
    case 'updateCheckbox':
       var arr = Object.assign(state);
       arr = state.map(stateNode => {
            if (stateNode.node == action.payload.node){
                if (action.payload.value == 'flip')
                {
                  stateNode.selected = !stateNode.selected;
                }
                else{
                  stateNode.selected = action.payload.value;
                }

            }
            return stateNode;
        });
        return [...arr];
    case 'updateCheckboxes':
       const arr2 = state.map((stateNode, index) => {
            const nodeToUpdate = action.payload.filter( node => stateNode.node == node.node);
            if (nodeToUpdate.length > 0){
                stateNode.selected = nodeToUpdate[0].value;
            }
            return stateNode;
        });
        return [...arr2];
    default:
      return state;
  }
};

export const addNode = node => ({
  type: 'addNode',
  payload: node
});

export const setNodes = nodes => ({
  type: 'setNodes',
  payload: nodes
});

export const updateSelected = newValue => ({
  type: 'updateSelected',
  payload: newValue
});

export const updateCheckbox = newValue => ({
  type: 'updateCheckbox',
  payload: newValue
});

export const updateCheckboxes = newValue => ({
  type: 'updateCheckboxes',
  payload: newValue
});
