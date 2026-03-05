import React from 'react';
import { Routes, Route, useNavigate, useLocation } from 'react-router-dom';
import { ProLayout } from '@ant-design/pro-components';
import {
  HomeOutlined,
  UserOutlined,
  TeamOutlined,
  FunnelPlotOutlined,
  ScheduleOutlined,
} from '@ant-design/icons';
import DashboardHome from './pages/DashboardHome';
import LeadsPage from './pages/LeadsPage';
import CustomersPage from './pages/CustomersPage';
import OpportunitiesPage from './pages/OpportunitiesPage';
import ActivitiesPage from './pages/ActivitiesPage';

const menuRoutes = {
  route: {
    path: '/',
    routes: [
      {
        path: '/',
        name: '首页概览',
        icon: <HomeOutlined />,
      },
      {
        path: '/leads',
        name: '线索管理',
        icon: <UserOutlined />,
      },
      {
        path: '/customers',
        name: '客户管理',
        icon: <TeamOutlined />,
      },
      {
        path: '/opportunities',
        name: '商机管理',
        icon: <FunnelPlotOutlined />,
      },
      {
        path: '/activities',
        name: '活动记录',
        icon: <ScheduleOutlined />,
      },
    ],
  },
};

const App: React.FC = () => {
  const navigate = useNavigate();
  const location = useLocation();

  return (
    <ProLayout
      title="CRM 管理系统"
      logo={false}
      layout="mix"
      fixSiderbar
      fixedHeader
      {...menuRoutes}
      location={{ pathname: location.pathname }}
      menuItemRender={(item, dom) => (
        <a
          onClick={(e) => {
            e.preventDefault();
            if (item.path) navigate(item.path);
          }}
        >
          {dom}
        </a>
      )}
      token={{
        header: {
          colorBgHeader: '#fff',
        },
        sider: {
          colorMenuBackground: '#fff',
        },
      }}
    >
      <Routes>
        <Route path="/" element={<DashboardHome />} />
        <Route path="/leads" element={<LeadsPage />} />
        <Route path="/customers" element={<CustomersPage />} />
        <Route path="/opportunities" element={<OpportunitiesPage />} />
        <Route path="/activities" element={<ActivitiesPage />} />
      </Routes>
    </ProLayout>
  );
};

export default App;
