module obi_top (
    input  wire clk,
    input  wire rst,

    // OBI flattened signals (manager to subordinate)
    input  wire        s_obi_req,
    output wire        s_obi_gnt,
    input  wire [31:0] s_obi_addr,
    input  wire        s_obi_we,
    input  wire [3:0]  s_obi_be,
    input  wire [31:0] s_obi_wdata,
    input  wire [0:0]  s_obi_aid,

    // Response
    output wire        s_obi_rvalid,
    input  wire        s_obi_rready,
    output wire [31:0] s_obi_rdata,
    output wire        s_obi_err,
    output wire [0:0]  s_obi_rid
);

// Purely a shell so cocotb BFMs can drive/observe pins.

endmodule


