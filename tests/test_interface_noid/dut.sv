module dut
#(
        integer G_REGWIDTH = 32
      , integer G_ADDR_WIDTH = 32
)
(
        input  wire clk,
        input  wire rst,

        // Host-facing OBI (no aid/rid)
        input  wire        s_obi_req,
        output wire        s_obi_gnt,
        input  wire [G_ADDR_WIDTH-1:0] s_obi_addr,
        input  wire        s_obi_we,
        input  wire [(G_REGWIDTH/8)-1:0] s_obi_be,
        input  wire [G_REGWIDTH-1:0] s_obi_wdata,
        output wire        s_obi_rvalid,
        input  wire        s_obi_rready,
        output wire [G_REGWIDTH-1:0] s_obi_rdata,
        output wire        s_obi_err,

        // Device-facing OBI (no aid/rid)
        output wire        m_obi_req,
        input  wire        m_obi_gnt,
        output wire [G_ADDR_WIDTH-1:0] m_obi_addr,
        output wire        m_obi_we,
        output wire [(G_REGWIDTH/8)-1:0] m_obi_be,
        output wire [G_REGWIDTH-1:0] m_obi_wdata,
        input  wire        m_obi_rvalid,
        output wire        m_obi_rready,
        input  wire [G_REGWIDTH-1:0] m_obi_rdata,
        input  wire        m_obi_err
);

assign m_obi_req    = s_obi_req;
assign m_obi_addr   = s_obi_addr;
assign m_obi_we     = s_obi_we;
assign m_obi_be     = s_obi_be;
assign m_obi_wdata  = s_obi_wdata;
assign m_obi_rready = s_obi_rready;

assign s_obi_gnt    = m_obi_gnt;
assign s_obi_rvalid = m_obi_rvalid;
assign s_obi_rdata  = m_obi_rdata;
assign s_obi_err    = m_obi_err;

endmodule
