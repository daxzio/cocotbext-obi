module dut (
    input  wire clk,
    input  wire rst,

    // Host-facing OBI (manager VIP)
    input  wire        s_obi_req,
    output wire        s_obi_gnt,
    input  wire [31:0] s_obi_addr,
    input  wire        s_obi_we,
    input  wire [3:0]  s_obi_be,
    input  wire [31:0] s_obi_wdata,
    input  wire [0:0]  s_obi_aid,
    output wire        s_obi_rvalid,
    input  wire        s_obi_rready,
    output wire [31:0] s_obi_rdata,
    output wire        s_obi_err,
    output wire [0:0]  s_obi_rid,

    // Device-facing OBI (subordinate VIP)
    output wire        m_obi_req,
    input  wire        m_obi_gnt,
    output wire [31:0] m_obi_addr,
    output wire        m_obi_we,
    output wire [3:0]  m_obi_be,
    output wire [31:0] m_obi_wdata,
    output wire [0:0]  m_obi_aid,
    input  wire        m_obi_rvalid,
    output wire        m_obi_rready,
    input  wire [31:0] m_obi_rdata,
    input  wire        m_obi_err,
    input  wire [0:0]  m_obi_rid
);

// Loopback so each VIP drives DUT inputs and samples DUT outputs.
// A pin-only s_obi_* shell fails BFM-to-BFM suites because the
// simulator cannot deposit onto undriven DUT outputs.

assign m_obi_req    = s_obi_req;
assign m_obi_addr   = s_obi_addr;
assign m_obi_we     = s_obi_we;
assign m_obi_be     = s_obi_be;
assign m_obi_wdata  = s_obi_wdata;
assign m_obi_aid    = s_obi_aid;
assign m_obi_rready = s_obi_rready;

assign s_obi_gnt    = m_obi_gnt;
assign s_obi_rvalid = m_obi_rvalid;
assign s_obi_rdata  = m_obi_rdata;
assign s_obi_err    = m_obi_err;
assign s_obi_rid    = m_obi_rid;

endmodule
