import { useState, useEffect } from 'react';
import { 
  Share2, Trash2, Edit2, Plus, Check, X, Calendar, List, Database, 
  PlusCircle, Clock, Tv, Video, Music, Globe, MessageSquare, AlertCircle, ExternalLink, 
  ArrowUp, ArrowDown, Folder, Tag, Sparkles, AlertTriangle
} from 'lucide-react';
import GlassCard from '../components/glass/GlassCard';
import GlassButton from '../components/glass/GlassButton';
import GlassModal from '../components/glass/GlassModal';
import { browsePath } from '../api/client';

// Types matching backend Pydantic schemas
interface TimeSlot {
  id?: number;
  channel_id?: string;
  posting_time: string;
  active: number;
}

interface Channel {
  id: string;
  platform: string;
  channel_name: string;
  channel_avatar: string | null;
  auth_data: any;
  daily_limit: number;
  status: string;
  created_at: string;
  time_slots: TimeSlot[];
}

interface ProductAffiliate {
  id: string;
  product_name: string;
  product_tag: string;
  affiliate_link: string;
  description: string | null;
  created_at: string;
}

interface QueueItem {
  id: string;
  channel_id: string;
  channel_name: string;
  platform: string;
  video_path: string;
  title: string;
  caption: string | null;
  hashtags: string | null;
  product_link: string | null;
  scheduled_time: string;
  status: string;
  error_message: string | null;
  created_at: string;
}

export default function FleetPage() {
  const [activeTab, setActiveTab] = useState<'queue' | 'channels' | 'products'>('queue');
  
  // Data states
  const [queue, setQueue] = useState<QueueItem[]>([]);
  const [channels, setChannels] = useState<Channel[]>([]);
  const [products, setProducts] = useState<ProductAffiliate[]>([]);
  
  // Loading & Message states
  const [loading, setLoading] = useState(false);
  const [notification, setNotification] = useState<{ message: string; type: 'success' | 'error' } | null>(null);

  // Queue pagination
  const QUEUE_PAGE_SIZE = 10;
  const [queuePage, setQueuePage] = useState(1);

  // Modals state
  const [showAddChannel, setShowAddChannel] = useState(false);
  const [showAddProduct, setShowAddProduct] = useState(false);
  const [showGenerateQueue, setShowGenerateQueue] = useState(false);
  const [editingProduct, setEditingProduct] = useState<ProductAffiliate | null>(null);
  const [editingQueueItem, setEditingQueueItem] = useState<QueueItem | null>(null);

  // Form states
  const [newChannel, setNewChannel] = useState({
    platform: 'youtube',
    channel_name: '',
    daily_limit: 5,
    auth_data_json: '',
    time_slots_str: '11:30, 18:00, 20:30'
  });
  
  const [newProduct, setNewProduct] = useState({
    product_name: '',
    product_tag: '',
    affiliate_link: '',
    description: ''
  });

  const [generateConfig, setGenerateConfig] = useState({
    folder_path: '',
    selected_channels: [] as string[],
    tags_str: ''
  });

  // Fetch all data
  const fetchData = async () => {
    setLoading(true);
    try {
      const [resQueue, resChannels, resProducts] = await Promise.all([
        fetch('/api/fleet/queue').then(r => r.json()),
        fetch('/api/fleet/channels').then(r => r.json()),
        fetch('/api/fleet/products').then(r => r.json())
      ]);
      setQueue(resQueue);
      setChannels(resChannels);
      setProducts(resProducts);
      setQueuePage(1); // Reset pagination on refresh
    } catch (err) {
      showToast('Không thể tải dữ liệu từ server.', 'error');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, []);

  const showToast = (message: string, type: 'success' | 'error') => {
    setNotification({ message, type });
    setTimeout(() => setNotification(null), 4000);
  };

  // Channel Operations
  const handleAddChannel = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newChannel.channel_name.trim()) return showToast('Vui lòng điền tên kênh.', 'error');
    
    let parsedAuth = {};
    try {
      parsedAuth = JSON.parse(newChannel.auth_data_json || '{}');
    } catch (err) {
      return showToast('Cấu hình xác thực (JSON) không hợp lệ.', 'error');
    }

    const slots = newChannel.time_slots_str
      .split(',')
      .map(s => s.trim())
      .filter(s => /^\d{2}:\d{2}$/.test(s));

    try {
      const res = await fetch('/api/fleet/channels', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          platform: newChannel.platform,
          channel_name: newChannel.channel_name,
          daily_limit: newChannel.daily_limit,
          auth_data: parsedAuth,
          time_slots: slots
        })
      });
      
      if (!res.ok) throw new Error(await res.text());
      
      showToast('Đã liên kết kênh thành công.', 'success');
      setShowAddChannel(false);
      setNewChannel({
        platform: 'youtube',
        channel_name: '',
        daily_limit: 5,
        auth_data_json: '',
        time_slots_str: '11:30, 18:00, 20:30'
      });
      fetchData();
    } catch (err: any) {
      showToast(`Lỗi: ${err.message || 'Không thể kết nối kênh.'}`, 'error');
    }
  };

  const handleDeleteChannel = async (id: string) => {
    if (!confirm('Bạn có chắc chắn muốn hủy liên kết kênh này và xóa lịch trình liên quan?')) return;
    try {
      const res = await fetch(`/api/fleet/channels/${id}`, { method: 'DELETE' });
      if (!res.ok) throw new Error();
      showToast('Đã hủy liên kết kênh.', 'success');
      fetchData();
    } catch (err) {
      showToast('Không thể xóa kênh.', 'error');
    }
  };

  // Product Operations
  const handleSaveProduct = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newProduct.product_name.trim() || !newProduct.product_tag.trim() || !newProduct.affiliate_link.trim()) {
      return showToast('Vui lòng điền đầy đủ các trường bắt buộc.', 'error');
    }

    const isEdit = Boolean(editingProduct);
    const url = isEdit ? `/api/fleet/products/${editingProduct?.id}` : '/api/fleet/products';
    const method = isEdit ? 'PUT' : 'POST';

    try {
      const res = await fetch(url, {
        method,
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(newProduct)
      });
      
      if (!res.ok) throw new Error();
      
      showToast(isEdit ? 'Đã cập nhật sản phẩm.' : 'Đã thêm sản phẩm mới thành công.', 'success');
      setShowAddProduct(false);
      setEditingProduct(null);
      setNewProduct({ product_name: '', product_tag: '', affiliate_link: '', description: '' });
      fetchData();
    } catch (err) {
      showToast('Lỗi khi lưu sản phẩm.', 'error');
    }
  };

  const handleDeleteProduct = async (id: string) => {
    if (!confirm('Xóa sản phẩm tiếp thị này?')) return;
    try {
      const res = await fetch(`/api/fleet/products/${id}`, { method: 'DELETE' });
      if (!res.ok) throw new Error();
      showToast('Đã xóa sản phẩm.', 'success');
      fetchData();
    } catch (err) {
      showToast('Không thể xóa sản phẩm.', 'error');
    }
  };

  // Queue Operations
  const handleUpdateQueueItem = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!editingQueueItem) return;

    try {
      const res = await fetch(`/api/fleet/queue/${editingQueueItem.id}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          title: editingQueueItem.title,
          caption: editingQueueItem.caption,
          hashtags: editingQueueItem.hashtags,
          product_link: editingQueueItem.product_link,
          scheduled_time: editingQueueItem.scheduled_time,
          status: editingQueueItem.status
        })
      });
      
      if (!res.ok) throw new Error();
      
      showToast('Đã lưu thông tin lịch đăng bài.', 'success');
      setEditingQueueItem(null);
      fetchData();
    } catch (err) {
      showToast('Không thể cập nhật mục hàng đợi.', 'error');
    }
  };

  const handleDeleteQueueItem = async (id: string) => {
    if (!confirm('Bạn có muốn xóa video này khỏi lịch đăng bài?')) return;
    try {
      const res = await fetch(`/api/fleet/queue/${id}`, { method: 'DELETE' });
      if (!res.ok) throw new Error();
      showToast('Đã xóa video khỏi hàng đợi.', 'success');
      fetchData();
    } catch (err) {
      showToast('Không thể xóa video khỏi hàng đợi.', 'error');
    }
  };

  // Reorder queue items up/down
  const handleMoveQueueItem = async (index: number, direction: 'up' | 'down') => {
    const targetIndex = direction === 'up' ? index - 1 : index + 1;
    if (targetIndex < 0 || targetIndex >= queue.length) return;

    const newQueue = [...queue];
    // Swap IDs but keep the schedule time indices intact (swap visual ordering)
    const tempId = newQueue[index].id;
    newQueue[index].id = newQueue[targetIndex].id;
    newQueue[targetIndex].id = tempId;

    const orderedIds = newQueue.map(item => item.id);
    
    try {
      const res = await fetch('/api/fleet/queue/reorder', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ queue_ids: orderedIds })
      });
      if (!res.ok) throw new Error();
      fetchData();
    } catch (err) {
      showToast('Lỗi khi sắp xếp lại hàng đợi.', 'error');
    }
  };

  // Auto Schedule Generation
  const handleGenerateQueue = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!generateConfig.folder_path.trim()) return showToast('Vui lòng nhập đường dẫn thư mục.', 'error');
    if (generateConfig.selected_channels.length === 0) return showToast('Vui lòng chọn ít nhất một kênh.', 'error');

    setLoading(true);
    try {
      const res = await fetch('/api/fleet/queue/generate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          folder_path: generateConfig.folder_path,
          channel_ids: generateConfig.selected_channels,
          tags: generateConfig.tags_str ? generateConfig.tags_str.split(',').map(t => t.trim()) : null
        })
      });
      
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Lỗi lập lịch.');
      
      showToast(data.message || 'Lập lịch tự động chéo kênh thành công.', 'success');
      setShowGenerateQueue(false);
      setGenerateConfig({ folder_path: '', selected_channels: [], tags_str: '' });
      fetchData();
    } catch (err: any) {
      showToast(err.message || 'Lập lịch tự động thất bại.', 'error');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="relative min-h-screen p-6 text-slate-100 bg-slate-950/20 select-none">
      
      {/* Toast Notification */}
      {notification && (
        <div className={`fixed right-6 top-6 z-50 flex items-center gap-2.5 rounded-lg border px-4 py-3 shadow-2xl transition-all duration-300 animate-slide-in-right ${
          notification.type === 'success' 
            ? 'border-cyan-500/30 bg-cyan-950/80 text-cyan-200 shadow-cyan-950/20' 
            : 'border-rose-500/30 bg-rose-950/80 text-rose-200 shadow-rose-950/20'
        }`}>
          <AlertCircle size={18} className={notification.type === 'success' ? 'text-cyan-400' : 'text-rose-400'} />
          <span className="text-sm font-medium">{notification.message}</span>
        </div>
      )}

      {/* Header & Main Tabs */}
      <div className="flex flex-col gap-6 md:flex-row md:items-center md:justify-between border-b border-white/5 pb-5">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-white flex items-center gap-2">
            <Share2 className="text-cyan-400" size={24} />
            Hệ thống Phân phối Đa kênh Tự động
          </h1>
          <p className="mt-1 text-sm text-slate-400">
            Lập lịch, quản lý kênh, tự động sinh AI content và đính kèm link tiếp thị sản phẩm.
          </p>
        </div>

        {/* Tab Selector */}
        <div className="flex rounded-lg bg-black/40 p-1 border border-white/5 shadow-inner self-start">
          <TabButton active={activeTab === 'queue'} icon={<Calendar size={15} />} label="Hàng đợi & Lịch trình" onClick={() => setActiveTab('queue')} />
          <TabButton active={activeTab === 'channels'} icon={<Tv size={15} />} label="Kênh liên kết" onClick={() => setActiveTab('channels')} />
          <TabButton active={activeTab === 'products'} icon={<Database size={15} />} label="Kho sản phẩm" onClick={() => setActiveTab('products')} />
        </div>
      </div>

      {/* Primary Content View */}
      <div className="mt-6">
        
        {/* Tab 1: Queue & Timeline */}
        {activeTab === 'queue' && (
          <div className="grid gap-6">
            <div className="flex items-center justify-between">
              <h2 className="text-lg font-semibold text-white flex items-center gap-1.5">
                <Clock className="text-cyan-400" size={18} />
                Hàng đợi phát sóng ({queue.length} video)
              </h2>
              <div className="flex gap-2">
                <GlassButton variant="primary" onClick={() => setShowGenerateQueue(true)}>
                  <Sparkles size={15} className="mr-1.5 text-slate-950" />
                  Lập lịch tự động từ Folder
                </GlassButton>
              </div>
            </div>

            {queue.length === 0 ? (
              <GlassCard className="flex flex-col items-center justify-center p-12 text-center border border-white/5">
                <Calendar size={48} className="text-slate-600 mb-4" />
                <p className="text-slate-400 font-medium">Hàng đợi đăng bài hiện đang rỗng.</p>
                <p className="text-xs text-slate-500 mt-1 max-w-sm">
                  Hãy liên kết các tài khoản mạng xã hội và nhấp nút "Lập lịch tự động" để phân phối video hàng loạt.
                </p>
              </GlassCard>
            ) : (
              <div className="grid gap-4">
                {queue
                  .slice((queuePage - 1) * QUEUE_PAGE_SIZE, queuePage * QUEUE_PAGE_SIZE)
                  .map((item, index) => {
                    const globalIndex = (queuePage - 1) * QUEUE_PAGE_SIZE + index;
                    return (
                  <GlassCard 
                    key={item.id}
                    className={`border border-white/10 p-4 transition-all duration-300 hover:border-cyan-300/20 ${
                      item.status === 'success' ? 'border-cyan-500/20 bg-cyan-950/5' :
                      item.status === 'failed' ? 'border-rose-500/20 bg-rose-950/5' :
                      item.status === 'publishing' ? 'border-amber-500/30 bg-amber-950/10 shadow-[0_0_15px_rgba(245,158,11,0.05)] animate-pulse' : ''
                    }`}
                  >
                    <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
                      
                      {/* Video Info */}
                      <div className="flex items-center gap-4 min-w-0 flex-1">
                        
                        {/* Platform Indicator */}
                        <div className={`p-2.5 rounded-lg flex items-center justify-center border shrink-0 ${
                          item.platform === 'youtube' ? 'bg-rose-500/10 border-rose-500/20 text-rose-400' :
                          item.platform === 'tiktok' ? 'bg-teal-500/10 border-teal-500/20 text-teal-400' :
                          'bg-blue-500/10 border-blue-500/20 text-blue-400'
                        }`}>
                          {item.platform === 'youtube' ? <Video size={20} /> :
                           item.platform === 'tiktok' ? <Music size={20} /> :
                           <Globe size={20} />}
                        </div>

                        <div className="min-w-0 flex-1">
                          <div className="flex flex-wrap items-center gap-2">
                            <h3 className="font-semibold text-sm text-white truncate" title={item.title}>
                              {item.title}
                            </h3>
                            <span className="text-[10px] px-2 py-0.5 rounded-full border bg-black/30 border-white/5 text-slate-400">
                              Kênh: {item.channel_name}
                            </span>
                            <span className={`text-[10px] font-semibold uppercase tracking-wider px-2 py-0.5 rounded ${
                              item.status === 'success' ? 'bg-cyan-500/10 text-cyan-400 border border-cyan-400/20' :
                              item.status === 'failed' ? 'bg-rose-500/10 text-rose-400 border border-rose-400/20' :
                              item.status === 'publishing' ? 'bg-amber-500/10 text-amber-400 border border-amber-400/20' :
                              'bg-slate-800/50 text-slate-400 border border-slate-700'
                            }`}>
                              {item.status === 'success' ? 'Đã đăng' :
                               item.status === 'failed' ? 'Thất bại' :
                               item.status === 'publishing' ? 'Đang tải lên' : 'Chờ đăng'}
                            </span>
                          </div>

                          <p className="text-[11px] text-slate-400 mt-1 truncate" title={item.video_path}>
                            File: {item.video_path.split(/[\\/]/).pop()}
                          </p>

                          {/* Preview AI caption */}
                          {(item.caption || item.product_link) && (
                            <div className="mt-2 text-xs text-slate-300 bg-black/20 rounded border border-white/5 p-2 leading-relaxed">
                              {item.caption && <p className="italic text-slate-400">"{item.caption}"</p>}
                              {item.product_link && (
                                <p className="mt-1 text-cyan-300 flex items-center gap-1">
                                  <Tag size={11} /> Link ghim: <span className="underline select-all">{item.product_link}</span>
                                </p>
                              )}
                            </div>
                          )}

                          {/* Error message logging */}
                          {item.error_message && (
                            <div className="mt-2 text-xs text-rose-300 bg-rose-950/15 border border-rose-500/20 rounded p-2 flex items-start gap-1.5 leading-relaxed">
                              <AlertTriangle size={13} className="shrink-0 mt-0.5 text-rose-400" />
                              <div>Lỗi đăng tải: {item.error_message}</div>
                            </div>
                          )}
                        </div>
                      </div>

                      {/* Time Slot & Quick Actions */}
                      <div className="flex sm:flex-col items-end gap-3 self-stretch sm:self-auto shrink-0 border-t sm:border-t-0 border-white/5 pt-3 sm:pt-0">
                        
                        {/* Schedule Time badge */}
                        <div className="flex items-center gap-1.5 text-xs text-slate-300 bg-black/30 border border-white/5 rounded px-2.5 py-1">
                          <Clock size={13} className="text-cyan-400" />
                          <span>Lên lịch: <strong>{item.scheduled_time}</strong></span>
                        </div>

                        {/* Control buttons */}
                        <div className="flex items-center gap-1">
                          
                          {/* Reordering buttons (Only for pending items) */}
                          {item.status === 'pending' && (
                            <>
                              <button 
                                onClick={() => handleMoveQueueItem(globalIndex, 'up')}
                                disabled={globalIndex === 0}
                                className="p-1.5 rounded bg-white/5 text-slate-400 hover:text-white hover:bg-white/10 disabled:opacity-25"
                                title="Đẩy lịch lên trước"
                              >
                                <ArrowUp size={14} />
                              </button>
                              <button 
                                onClick={() => handleMoveQueueItem(globalIndex, 'down')}
                                disabled={globalIndex === queue.length - 1}
                                className="p-1.5 rounded bg-white/5 text-slate-400 hover:text-white hover:bg-white/10 disabled:opacity-25"
                                title="Đẩy lịch lùi sau"
                              >
                                <ArrowDown size={14} />
                              </button>
                            </>
                          )}

                          {/* Edit Details */}
                          <button 
                            onClick={() => {
                              setEditingQueueItem(item);
                            }}
                            className="p-1.5 rounded bg-white/5 text-slate-400 hover:text-cyan-300 hover:bg-cyan-950/20 border border-white/5"
                            title="Sửa nội dung hoặc thời gian đăng"
                          >
                            <Edit2 size={14} />
                          </button>

                          {/* Delete Item */}
                          <button 
                            onClick={() => handleDeleteQueueItem(item.id)}
                            className="p-1.5 rounded bg-white/5 text-slate-400 hover:text-rose-400 hover:bg-rose-950/20 border border-white/5"
                            title="Xóa khỏi lịch đăng"
                          >
                            <Trash2 size={14} />
                          </button>
                        </div>

                      </div>

                    </div>
                    </GlassCard>
                    );
                  })}

                {/* Queue Pagination */}
                {queue.length > QUEUE_PAGE_SIZE && (
                  <div className="flex items-center justify-between rounded-lg border border-white/10 bg-white/5 px-4 py-2.5">
                    <span className="text-xs text-slate-400">
                      Trang <span className="font-semibold text-white">{queuePage}</span>
                      /{Math.ceil(queue.length / QUEUE_PAGE_SIZE)}
                      <span className="ml-2 text-slate-500">· {queue.length} video</span>
                    </span>
                    <div className="flex items-center gap-1">
                      <button
                        onClick={() => setQueuePage((p) => Math.max(1, p - 1))}
                        disabled={queuePage === 1}
                        className="px-3 py-1 rounded-md text-xs font-medium border border-white/10 bg-white/5 text-slate-300 hover:bg-white/10 hover:text-white disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
                      >
                        ← Trước
                      </button>
                      <button
                        onClick={() => setQueuePage((p) => Math.min(Math.ceil(queue.length / QUEUE_PAGE_SIZE), p + 1))}
                        disabled={queuePage === Math.ceil(queue.length / QUEUE_PAGE_SIZE)}
                        className="px-3 py-1 rounded-md text-xs font-medium border border-white/10 bg-white/5 text-slate-300 hover:bg-white/10 hover:text-white disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
                      >
                        Tiếp →
                      </button>
                    </div>
                  </div>
                )}
              </div>
            )}
          </div>
        )}

        {/* Tab 2: Channels Management */}
        {activeTab === 'channels' && (
          <div className="grid gap-6">
            <div className="flex items-center justify-between">
              <h2 className="text-lg font-semibold text-white flex items-center gap-1.5">
                <Tv className="text-cyan-400" size={18} />
                Danh sách kênh liên kết ({channels.length} tài khoản)
              </h2>
              <GlassButton variant="primary" onClick={() => setShowAddChannel(true)}>
                <Plus size={16} className="mr-1 text-slate-950" />
                Liên kết kênh mới
              </GlassButton>
            </div>

            {channels.length === 0 ? (
              <GlassCard className="flex flex-col items-center justify-center p-12 text-center border border-white/5">
                <Tv size={48} className="text-slate-600 mb-4" />
                <p className="text-slate-400 font-medium">Chưa có kênh liên kết nào.</p>
                <p className="text-xs text-slate-500 mt-1 max-w-sm">
                  Nhấp vào "Liên kết kênh mới" để bắt đầu cấu hình đăng tải lên YouTube, Meta hoặc TikTok.
                </p>
              </GlassCard>
            ) : (
              <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
                {channels.map(channel => (
                  <GlassCard key={channel.id} className="border border-white/10 p-5 flex flex-col justify-between gap-5">
                    <div>
                      {/* Channel Card Header */}
                      <div className="flex items-start justify-between">
                        <div className="flex items-center gap-3">
                          <div className={`p-2 rounded-lg border shrink-0 ${
                            channel.platform === 'youtube' ? 'bg-rose-500/10 border-rose-500/20 text-rose-400' :
                            channel.platform === 'tiktok' ? 'bg-teal-500/10 border-teal-500/20 text-teal-400' :
                            'bg-blue-500/10 border-blue-500/20 text-blue-400'
                          }`}>
                            {channel.platform === 'youtube' ? <Video size={20} /> :
                             channel.platform === 'tiktok' ? <Music size={20} /> :
                             <Globe size={20} />}
                          </div>
                          <div>
                            <h3 className="font-bold text-white text-sm truncate max-w-[150px]" title={channel.channel_name}>
                              {channel.channel_name}
                            </h3>
                            <span className="text-[10px] uppercase text-slate-400 font-semibold tracking-wider">
                              {channel.platform}
                            </span>
                          </div>
                        </div>

                        <span className={`text-[10px] font-semibold px-2 py-0.5 rounded ${
                          channel.status === 'active' ? 'bg-cyan-500/10 text-cyan-400 border border-cyan-400/20' :
                          'bg-rose-500/10 text-rose-400 border border-rose-400/20'
                        }`}>
                          {channel.status === 'active' ? 'Hoạt động' : 'Lỗi Session'}
                        </span>
                      </div>

                      {/* Config details */}
                      <div className="mt-4 grid gap-1.5 text-xs text-slate-300">
                        <div className="flex justify-between">
                          <span className="text-slate-500">Video giới hạn/ngày:</span>
                          <span className="font-semibold">{channel.daily_limit} video</span>
                        </div>
                        <div className="flex justify-between">
                          <span className="text-slate-500">Khung giờ đăng:</span>
                          <span className="font-semibold truncate max-w-[140px]" title={channel.time_slots.map(s => s.posting_time).join(', ')}>
                            {channel.time_slots.length > 0 
                              ? channel.time_slots.map(s => s.posting_time).join(', ') 
                              : 'Chưa cấu hình'}
                          </span>
                        </div>
                      </div>
                    </div>

                    {/* Delete channel button */}
                    <div className="flex justify-end border-t border-white/5 pt-3">
                      <button
                        onClick={() => handleDeleteChannel(channel.id)}
                        className="text-xs text-slate-400 hover:text-rose-400 flex items-center gap-1 px-2.5 py-1.5 rounded hover:bg-rose-950/15 border border-transparent hover:border-rose-500/20 transition-all duration-200"
                      >
                        <Trash2 size={13} />
                        Hủy liên kết
                      </button>
                    </div>
                  </GlassCard>
                ))}
              </div>
            )}
          </div>
        )}

        {/* Tab 3: Product Database */}
        {activeTab === 'products' && (
          <div className="grid gap-6">
            <div className="flex items-center justify-between">
              <h2 className="text-lg font-semibold text-white flex items-center gap-1.5">
                <Database className="text-cyan-400" size={18} />
                Danh mục Sản phẩm tiếp thị ({products.length} sản phẩm)
              </h2>
              <GlassButton variant="primary" onClick={() => {
                setEditingProduct(null);
                setNewProduct({ product_name: '', product_tag: '', affiliate_link: '', description: '' });
                setShowAddProduct(true);
              }}>
                <Plus size={16} className="mr-1 text-slate-950" />
                Thêm sản phẩm mới
              </GlassButton>
            </div>

            {products.length === 0 ? (
              <GlassCard className="flex flex-col items-center justify-center p-12 text-center border border-white/5">
                <Database size={48} className="text-slate-600 mb-4" />
                <p className="text-slate-400 font-medium">Kho sản phẩm trống.</p>
                <p className="text-xs text-slate-500 mt-1 max-w-sm">
                  Hãy thêm liên kết sản phẩm tiếp thị cùng với từ khóa (tag) nhận diện để hệ thống tự động chèn vào bình luận ghim của video.
                </p>
              </GlassCard>
            ) : (
              <div className="grid gap-4 sm:grid-cols-2">
                {products.map(product => (
                  <GlassCard key={product.id} className="border border-white/10 p-5 flex flex-col justify-between gap-4">
                    <div className="min-w-0">
                      <div className="flex items-start justify-between gap-2">
                        <h3 className="font-bold text-white text-sm truncate" title={product.product_name}>
                          {product.product_name}
                        </h3>
                        <span className="shrink-0 flex items-center gap-1 text-[10px] font-semibold bg-cyan-950/40 text-cyan-300 border border-cyan-400/20 px-2 py-0.5 rounded-full">
                          <Tag size={10} />
                          {product.product_tag}
                        </span>
                      </div>

                      <p className="text-xs text-slate-400 mt-2 line-clamp-2" title={product.description || ''}>
                        {product.description || 'Không có mô tả sản phẩm.'}
                      </p>

                      <div className="mt-3 bg-black/30 border border-white/5 rounded px-2.5 py-1.5 text-xs text-cyan-300 truncate font-mono select-all flex items-center gap-1.5">
                        <ExternalLink size={12} className="shrink-0 text-slate-400" />
                        <span className="truncate" title={product.affiliate_link}>{product.affiliate_link}</span>
                      </div>
                    </div>

                    {/* Controls */}
                    <div className="flex items-center justify-end gap-2 border-t border-white/5 pt-3">
                      <button
                        onClick={() => {
                          setEditingProduct(product);
                          setNewProduct({
                            product_name: product.product_name,
                            product_tag: product.product_tag,
                            affiliate_link: product.affiliate_link,
                            description: product.description || ''
                          });
                          setShowAddProduct(true);
                        }}
                        className="text-xs text-slate-400 hover:text-cyan-300 flex items-center gap-1 px-2.5 py-1 rounded hover:bg-cyan-950/20 border border-transparent hover:border-cyan-400/20 transition duration-150"
                      >
                        <Edit2 size={12} />
                        Sửa
                      </button>
                      <button
                        onClick={() => handleDeleteProduct(product.id)}
                        className="text-xs text-slate-400 hover:text-rose-400 flex items-center gap-1 px-2.5 py-1 rounded hover:bg-rose-950/20 border border-transparent hover:border-rose-500/20 transition duration-150"
                      >
                        <Trash2 size={12} />
                        Xóa
                      </button>
                    </div>
                  </GlassCard>
                ))}
              </div>
            )}
          </div>
        )}

      </div>

      {/* MODAL 1: LINK NEW CHANNEL */}
      <GlassModal open={showAddChannel} title="Liên kết tài khoản/kênh mới" onClose={() => setShowAddChannel(false)}>
        <form onSubmit={handleAddChannel} className="grid gap-4 p-1">
          <div className="grid gap-1.5">
            <label className="text-xs font-semibold text-slate-400">Chọn Nền tảng</label>
            <select
              value={newChannel.platform}
              onChange={(e) => setNewChannel({ ...newChannel, platform: e.target.value })}
              className="bg-slate-900 border border-white/10 rounded-md p-2.5 text-sm text-white focus:outline-none focus:border-cyan-400"
            >
              <option value="youtube">YouTube (Tải lên chính thức)</option>
              <option value="meta">Facebook Page (Đăng Reels tự động)</option>
              <option value="tiktok">TikTok (Đăng tự động qua trình duyệt)</option>
            </select>
          </div>

          <div className="grid gap-1.5">
            <label className="text-xs font-semibold text-slate-400">Tên Kênh / Trang</label>
            <input
              type="text"
              value={newChannel.channel_name}
              onChange={(e) => setNewChannel({ ...newChannel, channel_name: e.target.value })}
              placeholder="ví dụ: @DecorThongMinh hoặc Page Tiện Ích Đời Sống"
              className="bg-slate-900 border border-white/10 rounded-md p-2.5 text-sm text-white focus:outline-none focus:border-cyan-400"
            />
          </div>

          <div className="grid gap-1.5">
            <label className="text-xs font-semibold text-slate-400">Hạn ngạch đăng bài tối đa (Số video / ngày)</label>
            <input
              type="number"
              value={newChannel.daily_limit}
              onChange={(e) => setNewChannel({ ...newChannel, daily_limit: parseInt(e.target.value) || 5 })}
              className="bg-slate-900 border border-white/10 rounded-md p-2.5 text-sm text-white focus:outline-none focus:border-cyan-400"
            />
          </div>

          <div className="grid gap-1.5">
            <label className="text-xs font-semibold text-slate-400">Khung giờ đăng cố định (Phân tách bằng dấu phẩy)</label>
            <input
              type="text"
              value={newChannel.time_slots_str}
              onChange={(e) => setNewChannel({ ...newChannel, time_slots_str: e.target.value })}
              placeholder="ví dụ: 11:30, 18:00, 20:30"
              className="bg-slate-900 border border-white/10 rounded-md p-2.5 text-sm text-white focus:outline-none focus:border-cyan-400"
            />
          </div>

          {/* Dynamic User-Friendly Instructions Guide */}
          <div className="rounded-md border border-cyan-500/20 bg-cyan-950/30 p-3.5 text-xs text-cyan-200 leading-relaxed">
            <h4 className="font-bold text-white mb-2 flex items-center gap-1">
              <Sparkles size={13} className="text-cyan-400" />
              Hướng dẫn lấy thông tin xác thực:
            </h4>
            {newChannel.platform === 'youtube' && (
              <ol className="list-decimal list-inside space-y-1 text-slate-300">
                <li>Truy cập <a href="https://console.cloud.google.com/" target="_blank" rel="noreferrer" className="text-cyan-400 underline inline-flex items-center gap-0.5">Google Cloud Console <ExternalLink size={10} /></a> và tạo dự án.</li>
                <li>Kích hoạt dịch vụ <strong>YouTube Data API v3</strong> trong thư viện API.</li>
                <li>Tại mục <strong>Credentials</strong>, tạo <strong>OAuth Client ID</strong> (chọn loại ứng dụng là <i>Desktop App</i>).</li>
                <li>Tải tệp mật JSON (client_secret.json) vừa tạo về máy tính.</li>
                <li>Mở tệp JSON đó bằng Notepad, sao chép toàn bộ nội dung và dán vào ô bên dưới.</li>
              </ol>
            )}
            {newChannel.platform === 'meta' && (
              <ol className="list-decimal list-inside space-y-1 text-slate-300">
                <li>Truy cập trang <a href="https://developers.facebook.com/" target="_blank" rel="noreferrer" className="text-cyan-400 underline inline-flex items-center gap-0.5">Facebook Developers <ExternalLink size={10} /></a> và tạo ứng dụng doanh nghiệp.</li>
                <li>Kích hoạt sản phẩm <strong>Page Reels Publishing</strong> trong trang quản trị ứng dụng.</li>
                <li>Sử dụng công cụ Graph API Explorer để tạo mã <strong>Access Token dài hạn</strong> (Page Token) của trang.</li>
                <li>Đảm bảo mã Token có đủ các quyền: <code className="text-[10px] bg-black/40 px-1 py-0.5 rounded text-amber-400">pages_show_list, pages_read_engagement, pages_manage_posts</code>.</li>
                <li>Dán mã token vào ô bên dưới dưới định dạng: <code className="text-[10px] bg-black/40 px-1.5 py-0.5 rounded text-cyan-300 select-all">{`{"access_token": "mã_token_của_bạn"}`}</code>.</li>
              </ol>
            )}
            {newChannel.platform === 'tiktok' && (
              <ol className="list-decimal list-inside space-y-1 text-slate-300">
                <li>Sử dụng Chrome cài đặt tiện ích mở rộng miễn phí <strong>Cookie-Editor</strong> từ Chrome Web Store.</li>
                <li>Đăng nhập tài khoản của bạn tại trang quản trị <a href="https://suatban.tiktok.com/" target="_blank" rel="noreferrer" className="text-cyan-400 underline inline-flex items-center gap-0.5">TikTok Studio <ExternalLink size={10} /></a>.</li>
                <li>Nhấp biểu tượng tiện ích <strong>Cookie-Editor</strong> trên thanh công cụ trình duyệt.</li>
                <li>Nhấn nút <strong>Export</strong> và chọn định dạng <strong>JSON</strong> để sao chép danh sách Cookies vào bộ nhớ tạm.</li>
                <li>Dán trực tiếp đoạn mã Cookies vừa sao chép vào ô cấu hình bên dưới.</li>
              </ol>
            )}
          </div>

          <div className="grid gap-1.5">
            <label className="text-xs font-semibold text-slate-400">
              Thông tin đăng nhập & Xác thực
            </label>
            <textarea
              rows={6}
              value={newChannel.auth_data_json}
              onChange={(e) => setNewChannel({ ...newChannel, auth_data_json: e.target.value })}
              placeholder={
                newChannel.platform === 'tiktok' 
                  ? '[\n  { "name": "sessionid", "value": "xxxx", "domain": ".tiktok.com" }\n]' 
                  : '{\n  "access_token": "xxxx",\n  "client_id": "xxxx",\n  "client_secret": "xxxx"\n}'
              }
              className="bg-slate-900 border border-white/10 rounded-md p-2.5 text-xs text-white font-mono focus:outline-none focus:border-cyan-400 leading-normal"
            />
          </div>

          <div className="flex justify-end gap-2 mt-4">
            <GlassButton type="button" variant="secondary" onClick={() => setShowAddChannel(false)}>Hủy</GlassButton>
            <GlassButton type="submit" variant="primary">Lưu Kênh</GlassButton>
          </div>
        </form>
      </GlassModal>

      {/* MODAL 2: ADD/EDIT PRODUCT */}
      <GlassModal 
        open={showAddProduct} 
        title={editingProduct ? 'Sửa thông tin sản phẩm' : 'Thêm sản phẩm tiếp thị mới'} 
        onClose={() => setShowAddProduct(false)}
      >
        <form onSubmit={handleSaveProduct} className="grid gap-4 p-1">
          <div className="grid gap-1.5">
            <label className="text-xs font-semibold text-slate-400">Tên Sản phẩm</label>
            <input
              type="text"
              value={newProduct.product_name}
              onChange={(e) => setNewProduct({ ...newProduct, product_name: e.target.value })}
              placeholder="ví dụ: Móc treo tường chịu lực silicon"
              className="bg-slate-900 border border-white/10 rounded-md p-2.5 text-sm text-white focus:outline-none focus:border-cyan-400"
            />
          </div>

          <div className="grid gap-1.5">
            <label className="text-xs font-semibold text-slate-400 flex items-center gap-1">
              Từ khóa nhận diện (Tag sản phẩm)
              <span className="text-[10px] text-slate-500 font-normal">(Trùng khớp với hashtag/tên file video)</span>
            </label>
            <input
              type="text"
              value={newProduct.product_tag}
              onChange={(e) => setNewProduct({ ...newProduct, product_tag: e.target.value })}
              placeholder="ví dụ: moc_treo"
              className="bg-slate-900 border border-white/10 rounded-md p-2.5 text-sm text-white focus:outline-none focus:border-cyan-400"
            />
          </div>

          <div className="grid gap-1.5">
            <label className="text-xs font-semibold text-slate-400">Đường dẫn tiếp thị liên kết (Affiliate URL)</label>
            <input
              type="text"
              value={newProduct.affiliate_link}
              onChange={(e) => setNewProduct({ ...newProduct, affiliate_link: e.target.value })}
              placeholder="ví dụ: https://shopee.vn/link-affiliate-cua-ban"
              className="bg-slate-900 border border-white/10 rounded-md p-2.5 text-sm text-white focus:outline-none focus:border-cyan-400"
            />
          </div>

          <div className="grid gap-1.5">
            <label className="text-xs font-semibold text-slate-400">Mô tả chi tiết</label>
            <textarea
              rows={3}
              value={newProduct.description}
              onChange={(e) => setNewProduct({ ...newProduct, description: e.target.value })}
              placeholder="Thông tin ghi chú về sản phẩm..."
              className="bg-slate-900 border border-white/10 rounded-md p-2.5 text-sm text-white focus:outline-none focus:border-cyan-400"
            />
          </div>

          <div className="flex justify-end gap-2 mt-4">
            <GlassButton type="button" variant="secondary" onClick={() => setShowAddProduct(false)}>Hủy</GlassButton>
            <GlassButton type="submit" variant="primary">Lưu Sản phẩm</GlassButton>
          </div>
        </form>
      </GlassModal>

      {/* MODAL 3: AUTO SCHEDULE GENERATE FROM FOLDER */}
      <GlassModal open={showGenerateQueue} title="Lập lịch tự động từ Thư mục video" onClose={() => setShowGenerateQueue(false)}>
        <form onSubmit={handleGenerateQueue} className="grid gap-4 p-1">
          
          <div className="grid gap-1.5">
            <label className="text-xs font-semibold text-slate-400">Đường dẫn thư mục video kết quả (.mp4)</label>
            <div className="grid gap-2 grid-cols-[1fr_auto]">
              <input
                type="text"
                value={generateConfig.folder_path}
                onChange={(e) => setGenerateConfig({ ...generateConfig, folder_path: e.target.value })}
                placeholder="ví dụ: D:\Data\Auto-Tool\Output\douyin_reup_xxx"
                className="bg-slate-900 border border-white/10 rounded-md p-2.5 text-sm text-white focus:outline-none focus:border-cyan-400 w-full"
              />
              <button
                type="button"
                onClick={async () => {
                  try {
                    const response = await browsePath({
                      mode: 'folder',
                      title: 'Chọn thư mục video kết quả',
                      initial_path: generateConfig.folder_path || null,
                    });
                    if (!response.cancelled && response.path) {
                      setGenerateConfig({ ...generateConfig, folder_path: response.path });
                    }
                  } catch (err) {
                    showToast('Không thể mở hộp thoại chọn thư mục.', 'error');
                  }
                }}
                className="bg-slate-800 hover:bg-slate-700 border border-white/10 rounded-md px-3 text-xs text-white font-semibold transition duration-150 focus:outline-none cursor-pointer"
              >
                Chọn thư mục
              </button>
            </div>
          </div>

          <div className="grid gap-1.5">
            <label className="text-xs font-semibold text-slate-400">Chọn các kênh phân phối chéo</label>
            <div className="grid gap-2 mt-1 max-h-[160px] overflow-y-auto border border-white/5 bg-black/20 rounded p-2.5">
              {channels.length === 0 ? (
                <span className="text-xs text-slate-500 italic">Không có kênh liên kết. Hãy tạo kênh trước.</span>
              ) : (
                channels.map(chan => (
                  <label key={chan.id} className="flex items-center gap-2 text-sm text-slate-300 cursor-pointer">
                    <input
                      type="checkbox"
                      checked={generateConfig.selected_channels.includes(chan.id)}
                      onChange={(e) => {
                        const updated = e.target.checked
                          ? [...generateConfig.selected_channels, chan.id]
                          : generateConfig.selected_channels.filter(id => id !== chan.id);
                        setGenerateConfig({ ...generateConfig, selected_channels: updated });
                      }}
                      className="rounded border-white/20 bg-slate-900 text-cyan-400 focus:ring-cyan-400/50"
                    />
                    <span className="flex items-center gap-1">
                      <strong>{chan.channel_name}</strong> ({chan.platform})
                    </span>
                  </label>
                ))
              )}
            </div>
          </div>

          <div className="grid gap-1.5">
            <label className="text-xs font-semibold text-slate-400 flex items-center gap-1">
              Thêm Hashtags / Tag bổ sung
              <span className="text-[10px] text-slate-500 font-normal">(Phân tách bằng dấu phẩy)</span>
            </label>
            <input
              type="text"
              value={generateConfig.tags_str}
              onChange={(e) => setGenerateConfig({ ...generateConfig, tags_str: e.target.value })}
              placeholder="ví dụ: #shorts, #giadungthongminh, #viral"
              className="bg-slate-900 border border-white/10 rounded-md p-2.5 text-sm text-white focus:outline-none focus:border-cyan-400"
            />
          </div>

          <div className="flex justify-end gap-2 mt-4">
            <GlassButton type="button" variant="secondary" onClick={() => setShowGenerateQueue(false)}>Hủy</GlassButton>
            <GlassButton type="submit" variant="primary" disabled={loading}>
              {loading ? 'Đang xử lý...' : 'Bắt đầu lập lịch'}
            </GlassButton>
          </div>
        </form>
      </GlassModal>

      {/* MODAL 4: EDIT QUEUE ITEM METADATA */}
      <GlassModal open={Boolean(editingQueueItem)} title="Chỉnh sửa thông tin lịch đăng bài" onClose={() => setEditingQueueItem(null)}>
        {editingQueueItem && (
          <form onSubmit={handleUpdateQueueItem} className="grid gap-4 p-1">
            <div className="grid gap-1.5">
              <label className="text-xs font-semibold text-slate-400">Tiêu đề video</label>
              <input
                type="text"
                value={editingQueueItem.title}
                onChange={(e) => setEditingQueueItem({ ...editingQueueItem, title: e.target.value })}
                className="bg-slate-900 border border-white/10 rounded-md p-2.5 text-sm text-white focus:outline-none focus:border-cyan-400"
              />
            </div>

            <div className="grid gap-1.5">
              <label className="text-xs font-semibold text-slate-400">Lời bình / Mô tả (Caption)</label>
              <textarea
                rows={3}
                value={editingQueueItem.caption || ''}
                onChange={(e) => setEditingQueueItem({ ...editingQueueItem, caption: e.target.value })}
                className="bg-slate-900 border border-white/10 rounded-md p-2.5 text-sm text-white focus:outline-none focus:border-cyan-400"
              />
            </div>

            <div className="grid gap-1.5">
              <label className="text-xs font-semibold text-slate-400">Hashtags</label>
              <input
                type="text"
                value={editingQueueItem.hashtags || ''}
                onChange={(e) => setEditingQueueItem({ ...editingQueueItem, hashtags: e.target.value })}
                className="bg-slate-900 border border-white/10 rounded-md p-2.5 text-sm text-white focus:outline-none focus:border-cyan-400"
              />
            </div>

            <div className="grid gap-1.5">
              <label className="text-xs font-semibold text-slate-400">Đường dẫn liên kết sản phẩm (Bình luận ghim)</label>
              <input
                type="text"
                value={editingQueueItem.product_link || ''}
                onChange={(e) => setEditingQueueItem({ ...editingQueueItem, product_link: e.target.value })}
                className="bg-slate-900 border border-white/10 rounded-md p-2.5 text-sm text-white focus:outline-none focus:border-cyan-400"
              />
            </div>

            <div className="grid gap-1.5">
              <label className="text-xs font-semibold text-slate-400">Thời gian phát sóng dự kiến (YYYY-MM-DD HH:MM:SS)</label>
              <input
                type="text"
                value={editingQueueItem.scheduled_time}
                onChange={(e) => setEditingQueueItem({ ...editingQueueItem, scheduled_time: e.target.value })}
                className="bg-slate-900 border border-white/10 rounded-md p-2.5 text-sm text-white focus:outline-none focus:border-cyan-400 font-mono"
              />
            </div>

            <div className="grid gap-1.5">
              <label className="text-xs font-semibold text-slate-400">Trạng thái đăng</label>
              <select
                value={editingQueueItem.status}
                onChange={(e) => setEditingQueueItem({ ...editingQueueItem, status: e.target.value })}
                className="bg-slate-900 border border-white/10 rounded-md p-2.5 text-sm text-white focus:outline-none focus:border-cyan-400"
              >
                <option value="pending">Chờ đăng (Pending)</option>
                <option value="success">Đăng thành công (Success)</option>
                <option value="failed">Đăng thất bại (Failed)</option>
              </select>
            </div>

            <div className="flex justify-end gap-2 mt-4">
              <GlassButton type="button" variant="secondary" onClick={() => setEditingQueueItem(null)}>Hủy</GlassButton>
              <GlassButton type="submit" variant="primary">Lưu thay đổi</GlassButton>
            </div>
          </form>
        )}
      </GlassModal>

    </div>
  );
}

function TabButton({ 
  active, icon, label, onClick 
}: { 
  active: boolean; icon: React.ReactNode; label: string; onClick: () => void 
}) {
  return (
    <button
      onClick={onClick}
      className={`flex items-center gap-2 px-4 py-2 rounded-md text-xs font-semibold transition-all duration-300 cursor-pointer ${
        active 
          ? 'bg-cyan-500/95 text-slate-950 shadow-md' 
          : 'text-slate-400 hover:text-white hover:bg-white/5'
      }`}
    >
      {icon}
      {label}
    </button>
  );
}
