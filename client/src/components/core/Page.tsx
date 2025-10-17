import React from 'react';
import './Page.css';

interface PageProps {
  children: React.ReactNode;
  title?: string;
  className?: string;
}

const Page: React.FC<PageProps> = ({ children, title, className = '' }) => {
  return (
    <div className={`page ${className}`}>
      {title && <h1 className="page-title">{title}</h1>}
      <div className="page-content">
        {children}
      </div>
    </div>
  );
};

export default Page;
