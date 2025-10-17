import React from 'react';
import './List.css';

interface ListProps {
  children: React.ReactNode;
  className?: string;
}

interface ListItemProps {
  children: React.ReactNode;
  onClick?: () => void;
  isSelected?: boolean;
  className?: string;
}

const List: React.FC<ListProps> & {
  Item: React.FC<ListItemProps>;
} = ({ children, className = '' }) => {
  return (
    <ul className={`list ${className}`}>
      {children}
    </ul>
  );
};

const ListItem: React.FC<ListItemProps> = ({
  children,
  onClick,
  isSelected = false,
  className = ''
}) => {
  return (
    <li
      className={`list-item ${isSelected ? 'list-item-selected' : ''} ${className}`}
      onClick={onClick}
      role={onClick ? 'button' : undefined}
      tabIndex={onClick ? 0 : undefined}
    >
      {children}
    </li>
  );
};

List.Item = ListItem;

export default List;
