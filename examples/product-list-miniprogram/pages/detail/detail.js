const ALL_PRODUCTS = [
  { id: 1, name: 'JavaScript 高级程序设计', price: 99, tag: '推荐' },
  { id: 2, name: '小程序开发入门', price: 59, tag: '新书' },
  { id: 3, name: 'Node.js 实战', price: 79, tag: '' },
  { id: 4, name: 'CSS 权威指南', price: 128, tag: '经典' },
  { id: 5, name: 'Vue.js 设计与实现', price: 119, tag: '推荐' },
  { id: 6, name: 'React 技术揭秘', price: 89, tag: '' },
  { id: 7, name: 'TypeScript 编程', price: 69, tag: '新书' },
  { id: 8, name: '算法导论', price: 128, tag: '经典' }
];

Page({
  data: { product: null },
  onLoad(options) {
    const id = parseInt(options.id, 10);
    const product = ALL_PRODUCTS.find(p => p.id === id) || null;
    this.setData({ product });
    if (product) {
      wx.setNavigationBarTitle({ title: product.name });
    }
  }
});
